"""Load shedding 룰. ESS와 Diesel 모두 못 막을 때 부하 차단 이벤트 발행.

설계 원칙 (rule-engine-spec §4.4):
  - 부하 차단은 자동 실행 금지 — operator 승인 후 실행.
  - 이 룰은 EVT-N-006 경고 이벤트만 발행한다.
  - 복구: net_power > 0 AND LOAD_SHED_HOLD_SECONDS 이상 경과 시 load restore 이벤트 발행.

부하 등급 (control_policy의 LOAD_PRIORITY_{device_id} 키):
  4 = 지연가능  → 가장 먼저 차단 대상
  3 = 일반      (기본값)
  2 = 중요
  1 = 필수      → 마지막 차단 대상
"""

import time as _time

PRIORITY = 20  # ESS/Diesel보다 낮음. 극단 상황에서만 동작.

# device_id → 차단 권고 발행 시각 (monotonic)
_shed_recommended_at: dict[str, float] = {}


def _load_priority(device_id: str, policy) -> int:
    key = f"LOAD_PRIORITY_{device_id}"
    raw = policy.get(key)
    if raw:
        return int(raw)
    return int(policy.get("LOAD_SHED_DEFAULT_PRIORITY") or 3)


def evaluate(flow: dict, policy, states: dict) -> list[dict]:
    net_power = flow["net_power"]
    load_p = flow["load_p"]
    now = _time.monotonic()
    hold_sec = policy.get("LOAD_SHED_HOLD_SECONDS") or 300.0

    events = []

    # --- 복구 판단 ---
    if net_power > 0 and _shed_recommended_at:
        for device_id, shed_at in list(_shed_recommended_at.items()):
            if now - shed_at >= hold_sec:
                events.append(_restore_event(device_id, net_power, now - shed_at))
                del _shed_recommended_at[device_id]
        return events

    # 부족 없음 → 비동작
    if net_power >= 0 or load_p <= 0:
        return []

    soc_low = policy.get("SOC_LOW")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")

    # task_018 §4.4 와 동일한 버그를 load 룰에서도 수정.
    # SOC 만 보지 말고 dispatchable 여부로 판단해야, 고립된 ESS 가
    # "처리 가능"으로 잘못 인식돼 shedding 이 막히는 문제 방지.
    dispatchable_ess = flow.get("dispatchable_ess_devices", [])
    if dispatchable_ess:
        any_can_discharge = any((e["SOC"] or 0) > soc_low for e in dispatchable_ess)
        if any_can_discharge:
            return []

    # Diesel 도 dispatchable 한 것만 본다 (토폴로지 고립된 디젤은 못 도와줌).
    dispatchable_diesel = flow.get("dispatchable_diesel_devices", [])
    for d in dispatchable_diesel:
        fuel = d.get("fuel_percent")
        has_fuel = fuel is None or fuel > fuel_critical
        if has_fuel:
            return []

    deficit = abs(net_power)

    load_targets = [
        (device_id, _load_priority(device_id, policy))
        for device_id, state in states.items()
        if state.get("resource_type") == "LOAD"
    ]
    load_targets.sort(key=lambda x: x[1], reverse=True)

    remaining_deficit = deficit
    for device_id, grade in load_targets:
        if remaining_deficit <= 0:
            break

        device_p = abs(states[device_id].get("reported_state", {}).get("P", 0) or 0)
        if device_p <= 0:
            continue
        if device_p >= remaining_deficit:
            reduction_ratio = round(min(remaining_deficit / device_p, 1.0), 3)
            remaining_deficit = 0
        else:
            reduction_ratio = 1.0
            remaining_deficit -= device_p

        # 동일 장치에 중복 권고 방지 (hold_sec 이내)
        if device_id in _shed_recommended_at:
            continue

        _shed_recommended_at[device_id] = now
        grade_label = {4: "지연가능", 3: "일반", 2: "중요", 1: "필수"}.get(grade, str(grade))
        events.append({
            "event_type": "EVT-N-006",
            "severity": "WARNING",
            "device_id": device_id,
            "resource_type": "load",
            "message": (
                f"부하 차단 검토 필요: deficit={deficit:.1f}kW, ESS/Diesel 불가, "
                f"등급={grade}({grade_label}), 권고차단율={reduction_ratio:.1%}"
            ),
            "payload": {
                "deficit_kw": round(deficit, 2),
                "reduction_ratio": reduction_ratio,
                "grade": grade,
            },
            "_is_event": True,
        })

    return events


def _restore_event(device_id: str, net_power: float, held_sec: float) -> dict:
    return {
        "event_type": "EVT-N-007",
        "severity": "INFO",
        "device_id": device_id,
        "resource_type": "load",
        "message": (
            f"부하 복구 검토 가능: net={net_power:.1f}kW 잉여, "
            f"차단 유지 {held_sec:.0f}s 경과"
        ),
        "payload": {"net_power_kw": round(net_power, 2), "held_sec": round(held_sec, 0)},
        "_is_event": True,
    }
