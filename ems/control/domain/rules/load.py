"""Load shedding 룰. ESS와 Diesel 모두 못 막을 때 마지막 수단으로 부하 차단."""


PRIORITY = 20  # ESS/Diesel보다 낮음. 극단 상황에서만 동작.


def evaluate(flow: dict, policy, states: dict) -> list[dict]:
    net_power = flow["net_power"]
    load_p = flow["load_p"]

    # 부족 없음 → 비동작
    if net_power >= 0 or load_p <= 0:
        return []

    soc_low = policy.get("SOC_LOW")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")

    # 가용 ESS가 있고 방전 가능하면 ESS가 먼저 처리 → load_shed 비동작
    ess_devices = flow["ess_devices"]
    if ess_devices:
        any_can_discharge = any((e["SOC"] or 0) > soc_low for e in ess_devices)
        if any_can_discharge:
            return []

    # Diesel이 돌고 있거나 기동 가능한 상태면 diesel이 먼저 처리 → load_shed 비동작
    diesel_devices = flow["diesel_devices"]
    for d in diesel_devices:
        fuel = d["fuel_percent"]
        has_fuel = fuel is None or fuel > fuel_critical
        if has_fuel:
            return []

    # 부족분 / 전체 부하 = 감축 비율. 0.0~1.0 범위로 클램프.
    reduction_ratio = round(min(abs(net_power) / load_p, 1.0), 3)

    commands = []
    load_targets = [
        device_id
        for device_id, state in states.items()
        if state.get("resource_type") == "LOAD"
    ]
    for device_id in load_targets:
        commands.append({
            "device_id": device_id,
            "resource_type": "load",
            "command_type": "load_shed",
            "payload": {"reduction_ratio": reduction_ratio},
            "reason": f"deficit={net_power:.1f}kW, ESS/Diesel unavailable",
            "priority": PRIORITY,
        })

    return commands
