"""Load shedding 룰. 두 가지 트리거를 지원한다 (현업 정석 2계층).

  1) 선제적 (proactive) — SoC 임계 기반:
     ESS 평균 SOC 가 SHED_SOC_TIER{N} 이하로 떨어지면 N 등급 이상 부하 차단 권고.
     net_power 가 잉여여도 동작 (선제 보호).
     예: SOC 25% → Tier 4 차단, SOC 15% → Tier 2 까지 차단.

  2) 반응적 (reactive) — net_power 기반 (기존 동작):
     net_power < 0 + ESS/Diesel 모두 처리 불가 → 등급 순 차단 권고.
     실제 부족 상황에서만 동작.

설계 원칙 (rule-engine-spec §4.4):
  - 부하 차단은 자동 실행 금지 — operator 승인 후 실행.
  - 이 룰은 EVT-N-006 경고 이벤트만 발행한다.
  - 복구: net_power > 0 AND LOAD_SHED_HOLD_SECONDS 이상 경과 + SoC 회복.

부하 등급 (control_policy의 LOAD_PRIORITY_{device_id} 키):
  4 = 지연가능  → 가장 먼저 차단 대상
  3 = 일반      (기본값)
  2 = 중요
  1 = 필수      → 절대 차단 X
"""

import time as _time

PRIORITY = 20  # ESS/Diesel보다 낮음. 극단 상황에서만 동작.

# device_id → 차단 권고 발행 시각 (monotonic)
_shed_recommended_at: dict[str, float] = {}

# SoC 임계 → 차단 시작 등급 매핑 (정책 키 → 등급).
# 순서 중요: 낮은 SOC 가 먼저 평가돼야 더 많은 등급 차단됨.
_SOC_TIER_KEYS = [
    ("SHED_SOC_TIER2", 2),  # SOC 15% 이하 → 등급 2 이상 차단 (Tier 1 제외 모두)
    ("SHED_SOC_TIER3", 3),  # SOC 20% 이하 → 등급 3 이상 차단
    ("SHED_SOC_TIER4", 4),  # SOC 25% 이하 → 등급 4 만 차단
]


def _load_priority(device_id: str, policy) -> int:
    key = f"LOAD_PRIORITY_{device_id}"
    raw = policy.get(key)
    if raw:
        return int(raw)
    return int(policy.get("LOAD_SHED_DEFAULT_PRIORITY") or 3)


def _avg_dispatchable_ess_soc(flow: dict) -> float | None:
    """dispatchable ESS 들의 평균 SOC. 없으면 None."""
    ess_list = flow.get("dispatchable_ess_devices") or []
    socs = [e["SOC"] for e in ess_list if e.get("SOC") is not None]
    if not socs:
        return None
    return sum(socs) / len(socs)


def _evaluate_soc_threshold_shed(flow: dict, policy, states: dict) -> list[dict]:
    """선제적 — SoC 임계 기반 단계 차단 권고.

    ESS 평균 SOC 가 SHED_SOC_TIER{N} 이하면 등급 N 이상 부하 차단 권고.
    net_power 가 잉여여도 동작 (사전 보호).
    디바운스는 _shed_recommended_at 공유.
    """
    avg_soc = _avg_dispatchable_ess_soc(flow)
    if avg_soc is None:
        return []  # ESS 없으면 SOC 트리거 의미 없음 (반응적 룰만)

    # 현재 SOC 에 의해 차단되어야 할 최소 등급 결정.
    # _SOC_TIER_KEYS 순회하면서 SOC 가 임계 이하면 그 등급을 차단 시작 등급으로.
    # 가장 낮은 SOC 임계가 먼저 평가되므로, 더 낮을수록 더 많은 등급 차단.
    min_grade_to_shed: int | None = None
    triggered_threshold: float | None = None
    triggered_key: str | None = None
    for key, grade in _SOC_TIER_KEYS:
        threshold = policy.get(key)
        if threshold is None:
            continue
        if avg_soc <= threshold:
            min_grade_to_shed = grade
            triggered_threshold = threshold
            triggered_key = key
            break  # 가장 엄격한 (낮은 SOC) 임계 만족 시 그 등급부터 차단

    if min_grade_to_shed is None:
        return []  # 어느 임계도 안 걸림

    now = _time.monotonic()
    events: list[dict] = []

    load_targets = [
        (device_id, _load_priority(device_id, policy))
        for device_id, state in states.items()
        if state.get("resource_type") == "LOAD"
    ]
    # 등급 큰 순서로 정렬 (등급 4 → 3 → 2 → 1)
    load_targets.sort(key=lambda x: x[1], reverse=True)

    for device_id, grade in load_targets:
        # min_grade_to_shed 이상 등급만 차단 대상
        if grade < min_grade_to_shed:
            continue
        # 디바운스
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
                f"부하 차단 검토 (선제): ESS 평균 SOC={avg_soc:.1f}% <= {triggered_threshold}% "
                f"({triggered_key}), 등급={grade}({grade_label})"
            ),
            "payload": {
                "trigger": "soc_threshold",
                "avg_soc": round(avg_soc, 2),
                "soc_threshold": triggered_threshold,
                "grade": grade,
                "min_grade_to_shed": min_grade_to_shed,
            },
            "_is_event": True,
        })

    return events


def evaluate(flow: dict, policy, states: dict) -> list[dict]:
    net_power = flow["net_power"]
    load_p = flow["load_p"]
    now = _time.monotonic()
    hold_sec = policy.get("LOAD_SHED_HOLD_SECONDS") or 300.0

    events = []

    # --- 1) 선제적 (SoC 임계 기반) — net_power 와 무관하게 평가 ---
    # 잉여 상태여도 SoC 가 낮으면 사전 차단 권고 (현업 정석).
    events.extend(_evaluate_soc_threshold_shed(flow, policy, states))

    # --- 2) 복구 판단 (잉여 + 디바운스 만료) ---
    if net_power > 0 and _shed_recommended_at:
        # SoC 트리거가 아직 활성이면 복구 보류 — _evaluate_soc_threshold_shed 에서
        # 같은 device 를 다시 _shed_recommended_at 에 넣었을 것이므로 자연스럽게 차단 유지됨.
        for device_id, shed_at in list(_shed_recommended_at.items()):
            if now - shed_at >= hold_sec:
                events.append(_restore_event(device_id, net_power, now - shed_at))
                del _shed_recommended_at[device_id]
        # SoC 임계 이벤트가 있으면 함께 반환, 없으면 복구 이벤트만.
        return events

    # 부족 없음 → 반응적 룰 비동작 (SoC 임계 이벤트만 있을 수 있음)
    if net_power >= 0 or load_p <= 0:
        return events

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
