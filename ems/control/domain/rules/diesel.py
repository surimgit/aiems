"""Diesel 룰. ESS만으로 부족분을 메울 수 없을 때 기동/정지/부하조정.

디젤 운전 상태는 telemetry에 없으므로 P 값으로 추정한다 (P>0 → running).
"""


PRIORITY = 30  # ESS보다 낮음. ESS가 충분하면 diesel 안 켜짐.


def evaluate(flow: dict, policy, states: dict) -> list[dict]:
    diesel_devices = flow["diesel_devices"]
    if not diesel_devices:
        return []

    diesel_start_soc = policy.get("DIESEL_START_SOC")
    diesel_stop_net = policy.get("DIESEL_STOP_NET_POWER")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")

    # ESS 가용 방전량 추정: SOC 충분한 ESS가 있는지
    ess_can_discharge = any(
        (e["SOC"] or 0) > diesel_start_soc for e in flow["ess_devices"]
    )

    net_power = flow["net_power"]
    commands = []

    for diesel in diesel_devices:
        running = (diesel["P"] or 0) > 0
        fuel = diesel["fuel_percent"]

        # 1. 연료 위급 → 강제 정지 (운전 중일 때만)
        if running and fuel is not None and fuel <= fuel_critical:
            commands.append(_stop(diesel, f"fuel_critical={fuel}%"))
            continue

        # 2. 부족 + ESS 방전 불가 → 기동
        if not running and net_power < 0 and not ess_can_discharge:
            commands.append(_start(diesel, f"net={net_power:.1f}kW, ESS unavailable"))
            continue

        # 3. 잉여 충분 → 정지
        if running and net_power > diesel_stop_net:
            commands.append(_stop(diesel, f"net={net_power:.1f}kW > {diesel_stop_net}"))
            continue

        # 4. 운전 중 + 부족 → 부족분 부하조정
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
