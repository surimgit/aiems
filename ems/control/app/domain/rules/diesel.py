"""Diesel 룰. ESS만으로 부족분을 메울 수 없을 때 기동/정지/부하조정.

정지 조건: net_power > DIESEL_STOP_NET_POWER AND 운전 시간 >= DIESEL_MIN_RUN_SECONDS
연료 위급은 최소 운전 시간 예외 (즉시 정지).

운전 시작 시각을 Redis에 저장해 process restart 후에도 최소 운전 시간 보장.
"""

import time as _time

PRIORITY = 30  # ESS보다 낮음. ESS가 충분하면 diesel 안 켜짐.

_DIESEL_MIN_RUN_SECONDS_DEFAULT = 300
_REDIS_PREFIX = "ems:diesel:start:"


async def evaluate(flow: dict, policy, states: dict, redis) -> list[dict]:
    diesel_devices = flow["diesel_devices"]
    if not diesel_devices:
        return []

    diesel_start_soc = policy.get("DIESEL_START_SOC")
    diesel_stop_net = policy.get("DIESEL_STOP_NET_POWER")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")
    min_run_sec = policy.get("DIESEL_MIN_RUN_SECONDS") or _DIESEL_MIN_RUN_SECONDS_DEFAULT

    # Phase D (PLAN_TOPOLOGY_AWARE_CONTROL.md):
    # SOC 만 보지 않고 dispatchable_ess_devices 사용.
    # → wire_fault / 토폴로지 고립 / fault 인 ESS 가 디젤 기동을 막지 않는다.
    ess_can_discharge = any(
        (e["SOC"] or 0) > diesel_start_soc
        for e in flow.get("dispatchable_ess_devices", [])
    )

    net_power = flow["net_power"]
    # ESS 가 이미 방전 중인 만큼을 제외한 diesel 몫의 net.
    # ESS p 는 net_power 에 포함되어 있으므로 빼서 diesel 이 담당할 실제 부족분만 본다.
    ess_p = flow.get("ess_p", 0.0)
    diesel_net = net_power - ess_p
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

        # 2. 부족 + ESS 방전 불가 → 기동
        if not running and net_power < 0 and not ess_can_discharge:
            commands.append(_start(diesel, f"net={net_power:.1f}kW, ESS unavailable"))
            continue

        # 3. 잉여 충분 → 정지 (ESS 포함 전체 net 기준, 최소 운전 시간 경과 후만)
        if running and net_power > diesel_stop_net:
            if running_seconds >= min_run_sec:
                commands.append(_stop(diesel, f"net={net_power:.1f}kW > {diesel_stop_net}, run={running_seconds:.0f}s"))
            else:
                remaining = min_run_sec - running_seconds
                print(f"[diesel] {device_id} 정지 보류: 최소 운전 시간 미달 ({running_seconds:.0f}s / {min_run_sec:.0f}s, {remaining:.0f}s 남음)")
            continue

        # 4. 운전 중 + diesel 몫 부족 → 부하조정 (ESS 방전분 제외한 diesel_net 기준)
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
