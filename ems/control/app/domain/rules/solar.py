"""Solar curtailment 룰. ESS가 충전 불가일 때 잉여 발전분만큼 출력 제한.
출력 제한 해제: net_power < 0 OR any(ESS.SOC < SOC_HIGH) 시 clear_curtailment 발행.

curtailment 상태를 Redis에 저장해 process restart 후에도 유지.
"""

PRIORITY = 20

_REDIS_PREFIX = "ems:curtailed:"


async def evaluate(flow: dict, policy, states: dict, redis) -> list[dict]:
    net_power = flow["net_power"]
    solar_p = flow["solar_p"]
    soc_high = policy.get("SOC_HIGH")
    # task_018 §4.4 와 동일한 패턴 보강: SOC 만 보지 말고 dispatchable 만 본다.
    # isolated ESS 는 SOC 낮아도 실제로 충전 못 받으므로 "충전 가능" 으로 보면 안 됨.
    dispatchable_ess = flow.get("dispatchable_ess_devices", [])

    any_can_charge = any((e["SOC"] or 0) < soc_high for e in dispatchable_ess) if dispatchable_ess else False

    commands = []
    solar_targets = [
        (device_id, state)
        for device_id, state in states.items()
        if state.get("resource_type") == "SOLAR"
    ]
    if not solar_targets:
        return []

    # --- 해제 조건: 부족 or ESS 충전 가능 ---
    if net_power <= 0 or any_can_charge:
        for device_id, state in solar_targets:
            key = f"{_REDIS_PREFIX}{device_id}"
            if await redis.exists(key):
                await redis.delete(key)
                commands.append({
                    "device_id": device_id,
                    "edge_id": state.get("edge_id"),
                    "resource_type": "solar",
                    "command_type": "clear_curtailment",
                    "payload": {},
                    "reason": f"net={net_power:.1f}kW or ESS can charge — curtailment 해제",
                    "priority": PRIORITY,
                })
        return commands

    # --- 제한 조건: 잉여 + ESS 만충 ---
    target_total_kw = max(solar_p - net_power, 0.0)
    per_device_limit = round(target_total_kw / len(solar_targets), 1)

    for device_id, state in solar_targets:
        await redis.set(f"{_REDIS_PREFIX}{device_id}", "1")
        commands.append({
            "device_id": device_id,
            "edge_id": state.get("edge_id"),
            "resource_type": "solar",
            "command_type": "curtailment",
            "payload": {"limit_kw": per_device_limit},
            "reason": f"surplus={net_power:.1f}kW, ESS full",
            "priority": PRIORITY,
        })

    return commands
