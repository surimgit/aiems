"""Solar curtailment 룰. ESS가 충전 불가일 때 잉여 발전분만큼 출력 제한."""


PRIORITY = 20  # ESS/Diesel보다 낮음. 극단 상황에서만 동작.


def evaluate(flow: dict, policy, states: dict) -> list[dict]:
    net_power = flow["net_power"]
    solar_p = flow["solar_p"]

    # 잉여 없음 → 비동작
    if net_power <= 0 or solar_p <= 0:
        return []

    soc_high = policy.get("SOC_HIGH")
    ess_devices = flow["ess_devices"]

    # 가용 ESS가 있고 모두 만충 상태가 아니면 ESS가 먼저 처리 → curtailment 비동작
    if ess_devices:
        any_can_charge = any((e["SOC"] or 0) < soc_high for e in ess_devices)
        if any_can_charge:
            return []

    commands = []
    solar_targets = [
        (device_id, state)
        for device_id, state in states.items()
        if state.get("resource_type") == "SOLAR"
    ]
    if not solar_targets:
        return []

    # 잉여분만큼 전체 solar 목표 출력을 깎는다. 대수로 균등 분배.
    target_total_kw = max(solar_p - net_power, 0.0)
    per_device_limit = round(target_total_kw / len(solar_targets), 1)

    for device_id, _state in solar_targets:
        commands.append({
            "device_id": device_id,
            "resource_type": "solar",
            "command_type": "curtailment",
            "payload": {"limit_kw": per_device_limit},
            "reason": f"surplus={net_power:.1f}kW, ESS full",
            "priority": PRIORITY,
        })

    return commands
