"""Load shedding 룰. ESS와 Diesel 모두 못 막을 때 마지막 수단으로 부하 차단.

부하 등급 (control_policy의 LOAD_PRIORITY_{device_id} 키):
  4 = 지연가능  → 가장 먼저 차단
  3 = 일반      → 두 번째 차단 (기본값)
  2 = 중요      → 세 번째 차단
  1 = 필수      → 마지막 차단 (불가피한 경우에만)
"""

PRIORITY = 20  # ESS/Diesel보다 낮음. 극단 상황에서만 동작.


def _load_priority(device_id: str, policy) -> int:
    """장치별 부하 등급 반환 (1~4). 미설정 시 기본값."""
    key = f"LOAD_PRIORITY_{device_id}"
    raw = policy.get(key)
    if raw:
        return int(raw)
    return int(policy.get("LOAD_SHED_DEFAULT_PRIORITY") or 3)


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

    # 부족분 계산
    deficit = abs(net_power)

    # 부하 장치를 등급 내림차순(4→3→2→1)으로 정렬 — 높은 등급부터 차단
    load_targets = [
        (device_id, _load_priority(device_id, policy))
        for device_id, state in states.items()
        if state.get("resource_type") == "LOAD"
    ]
    load_targets.sort(key=lambda x: x[1], reverse=True)

    commands = []
    remaining_deficit = deficit

    for device_id, grade in load_targets:
        if remaining_deficit <= 0:
            break

        # 해당 장치의 현재 전력 (P값)
        device_p = abs(states[device_id].get("P", 0) or 0)
        if device_p <= 0:
            # 전력 데이터 없으면 비율 방식으로 처리
            reduction_ratio = round(min(remaining_deficit / load_p, 1.0), 3)
            remaining_deficit = 0
        else:
            # 이 장치를 완전 차단하면 deficit을 다 커버할 수 있는지 확인
            if device_p >= remaining_deficit:
                reduction_ratio = round(min(remaining_deficit / device_p, 1.0), 3)
                remaining_deficit = 0
            else:
                reduction_ratio = 1.0
                remaining_deficit -= device_p

        grade_label = {4: "지연가능", 3: "일반", 2: "중요", 1: "필수"}.get(grade, str(grade))
        commands.append({
            "device_id": device_id,
            "resource_type": "load",
            "command_type": "load_shed",
            "payload": {"reduction_ratio": reduction_ratio},
            "reason": (
                f"deficit={deficit:.1f}kW, ESS/Diesel unavailable, "
                f"grade={grade}({grade_label}), reduction={reduction_ratio:.1%}"
            ),
            "priority": PRIORITY,
        })

    return commands
