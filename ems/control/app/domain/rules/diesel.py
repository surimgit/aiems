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

    ess_can_discharge = any(
        (e["SOC"] or 0) > diesel_start_soc for e in flow["ess_devices"]
    )

    net_power = flow["net_power"]
    now = _time.time()
    commands = []

    for diesel in diesel_devices:
        device_id = diesel["device_id"]
        operating_mode = (diesel.get("operating_mode") or "").lower()
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

        # 3. 잉여 충분 → 정지 (최소 운전 시간 경과 후만)
        if running and net_power > diesel_stop_net:
            if running_seconds >= min_run_sec:
                commands.append(_stop(diesel, f"net={net_power:.1f}kW > {diesel_stop_net}, run={running_seconds:.0f}s"))
            else:
                remaining = min_run_sec - running_seconds
                print(f"[diesel] {device_id} 정지 보류: 최소 운전 시간 미달 ({running_seconds:.0f}s / {min_run_sec:.0f}s, {remaining:.0f}s 남음)")
            continue

        # 4. 운전 중 + 부족 → 부하조정
        if running and net_power < 0:
            target_kw = round(abs(net_power) / len(diesel_devices), 1)
            commands.append(_load_control(diesel, target_kw, f"net={net_power:.1f}kW"))

    return commands


def _start(diesel: dict, reason: str) -> dict:
    return {
        "device_id": diesel["device_id"],
        "resource_type": "diesel",
        "command_type": "start",
        "payload": {},
        "reason": reason,
        "priority": PRIORITY,
    }


def _stop(diesel: dict, reason: str) -> dict:
    return {
        "device_id": diesel["device_id"],
        "resource_type": "diesel",
        "command_type": "stop",
        "payload": {},
        "reason": reason,
        "priority": PRIORITY,
    }


def _load_control(diesel: dict, target_kw: float, reason: str) -> dict:
    return {
        "device_id": diesel["device_id"],
        "resource_type": "diesel",
        "command_type": "load_control",
        "payload": {"target_kw": target_kw},
        "reason": reason,
        "priority": PRIORITY,
    }
