"""Diesel 룰. ESS만으로 부족분을 메울 수 없을 때 기동/정지/부하조정.

정지 조건: net_power > DIESEL_STOP_NET_POWER AND 운전 시간 >= DIESEL_MIN_RUN_SECONDS
연료 위급은 최소 운전 시간 예외 (즉시 정지).

운전 시작 시각을 Redis에 저장해 process restart 후에도 최소 운전 시간 보장.
"""

import time as _time

PRIORITY = 30  # ESS보다 낮음. ESS가 충분하면 diesel 안 켜짐.

_DIESEL_MIN_RUN_SECONDS_DEFAULT = 300
_REDIS_PREFIX = "ems:diesel:start:"


def _diesel_zone_deficit(diesel: dict, flow: dict, states: dict) -> float:
    """이 디젤이 연결된 load 구역들의 총 deficit.

    component_deficits 에서 이 디젤이 reachable_resources 에 포함된 load 항목만 합산.
    디젤이 꺼져있어도 '연결된 load 구역에 공급이 부족한가'를 판단하는 데 사용.
    """
    device_id = diesel["device_id"]
    total_deficit = 0.0
    for comp in flow.get("component_deficits", []):
        if device_id in comp.get("reachable_resources", []):
            total_deficit += comp.get("deficit_kw", 0.0)
    return total_deficit


def _diesel_zone_net(diesel: dict, flow: dict, states: dict) -> float:
    """이 디젤이 연결된 load 구역들의 총 (supply - load).

    양수 = 잉여, 음수 = 부족.
    """
    device_id = diesel["device_id"]
    zone_net = 0.0
    for comp in flow.get("component_deficits", []):
        if device_id in comp.get("reachable_resources", []):
            zone_net += comp.get("supply_kw", 0.0) - comp.get("load_kw", 0.0)
    return zone_net


async def evaluate(flow: dict, policy, states: dict, redis) -> list[dict]:
    diesel_devices = flow["diesel_devices"]
    if not diesel_devices:
        return []

    diesel_start_soc = policy.get("DIESEL_START_SOC")
    diesel_stop_net = policy.get("DIESEL_STOP_NET_POWER")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")
    min_run_sec = policy.get("DIESEL_MIN_RUN_SECONDS") or _DIESEL_MIN_RUN_SECONDS_DEFAULT

    # component_deficits 가 있으면 구역별 판단, 없으면 전역 net_power 로 fallback.
    use_zone = bool(flow.get("component_deficits"))
    net_power = flow["net_power"]
    ess_p = flow.get("ess_p", 0.0)

    now = _time.time()
    commands = []

    for diesel in diesel_devices:
        device_id = diesel["device_id"]
        operating_mode = (diesel.get("operating_mode") or "").lower()
        if operating_mode in ("fault", "error"):
            print(f"[diesel] {device_id} 제어 보류: FAULT 상태")
            continue

        running = operating_mode == "running" or (operating_mode == "" and (diesel["P"] or 0) > 0)
        fuel = diesel["fuel_percent"]
        redis_key = f"{_REDIS_PREFIX}{device_id}"

        # 운전 시작 시점 추적 (Redis)
        if running:
            if not await redis.exists(redis_key):
                await redis.set(redis_key, str(now))
        else:
            await redis.delete(redis_key)

        start_ts = await redis.get(redis_key)
        running_seconds = (now - float(start_ts)) if start_ts else 0.0

        # 1. 연료 위급 → 즉시 정지
        if running and fuel is not None and fuel <= fuel_critical:
            commands.append(_stop(diesel, f"fuel_critical={fuel}%"))
            continue

        if use_zone:
            # 토폴로지 기반: 이 디젤이 연결된 load 구역의 deficit/net 기준
            zone_deficit = _diesel_zone_deficit(diesel, flow, states)
            zone_net = _diesel_zone_net(diesel, flow, states)

            # 이 디젤이 연결된 load 구역에 직접(1홉) 연결된 dispatchable ESS 가 있는지 확인.
            zone_ess_can_discharge = False
            for comp in flow.get("component_deficits", []):
                if device_id not in comp.get("reachable_resources", []):
                    continue
                direct_ids = set(comp.get("direct_supply_ids", []))
                for e in flow.get("dispatchable_ess_devices", []):
                    if e["device_id"] in direct_ids and (e["SOC"] or 0) > diesel_start_soc:
                        zone_ess_can_discharge = True
                        break

            print(f"[debug][diesel] {device_id} running={running} zone_deficit={zone_deficit:.1f} zone_ess={zone_ess_can_discharge}")

            # 2. 구역 부족 + 구역 ESS 방전 불가 → 기동
            if not running and zone_deficit > 0 and not zone_ess_can_discharge:
                commands.append(_start(diesel, f"zone_deficit={zone_deficit:.1f}kW, zone_net={zone_net:.1f}kW"))
                continue

            # 3. 구역 잉여 충분 → 정지 (최소 운전 시간 경과 후)
            if running and zone_net > diesel_stop_net:
                if running_seconds >= min_run_sec:
                    commands.append(_stop(diesel, f"zone_net={zone_net:.1f}kW > {diesel_stop_net}, run={running_seconds:.0f}s"))
                else:
                    remaining = min_run_sec - running_seconds
                    print(f"[diesel] {device_id} 정지 보류: 최소 운전 시간 미달 ({running_seconds:.0f}s / {min_run_sec:.0f}s, {remaining:.0f}s 남음)")
                continue

            # 4. 운전 중 + 구역 부족 → 부하조정
            if running and zone_net < 0:
                target_kw = round(abs(zone_net) / len(diesel_devices), 1)
                commands.append(_load_control(diesel, target_kw, f"zone_net={zone_net:.1f}kW"))

        else:
            # fallback: 전역 net_power 기준 (토폴로지 없을 때)
            ess_can_discharge = any(
                (e["SOC"] or 0) > diesel_start_soc
                for e in flow.get("dispatchable_ess_devices", [])
            )
            diesel_net = net_power - ess_p

            if not running and net_power < 0 and not ess_can_discharge:
                commands.append(_start(diesel, f"net={net_power:.1f}kW, ESS unavailable"))
                continue

            if running and net_power > diesel_stop_net:
                if running_seconds >= min_run_sec:
                    commands.append(_stop(diesel, f"net={net_power:.1f}kW > {diesel_stop_net}, run={running_seconds:.0f}s"))
                else:
                    remaining = min_run_sec - running_seconds
                    print(f"[diesel] {device_id} 정지 보류: 최소 운전 시간 미달 ({running_seconds:.0f}s / {min_run_sec:.0f}s, {remaining:.0f}s 남음)")
                continue

            if running and diesel_net < 0:
                target_kw = round(abs(diesel_net) / len(diesel_devices), 1)
                commands.append(_load_control(diesel, target_kw, f"diesel_net={diesel_net:.1f}kW (net={net_power:.1f}, ess={ess_p:.1f})"))

    return commands


def _start(diesel: dict, reason: str) -> dict:
    return {
        "device_id": diesel["device_id"],
        "edge_id": diesel.get("edge_id"),
        "resource_type": "diesel",
        "command_type": "start",
        "payload": {},
        "reason": reason,
        "priority": PRIORITY,
    }


def _stop(diesel: dict, reason: str) -> dict:
    return {
        "device_id": diesel["device_id"],
        "edge_id": diesel.get("edge_id"),
        "resource_type": "diesel",
        "command_type": "stop",
        "payload": {},
        "reason": reason,
        "priority": PRIORITY,
    }


def _load_control(diesel: dict, target_kw: float, reason: str) -> dict:
    return {
        "device_id": diesel["device_id"],
        "edge_id": diesel.get("edge_id"),
        "resource_type": "diesel",
        "command_type": "load_control",
        "payload": {"target_kw": target_kw},
        "reason": reason,
        "priority": PRIORITY,
    }
