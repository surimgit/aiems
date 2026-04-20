from __future__ import annotations

from typing import Literal


OperatingMode = Literal["charge", "discharge", "standby"]
EssState = Literal[
    "IDLE",
    "STANDBY",
    "CHARGING",
    "DISCHARGING",
    "IN_PROGRESS",
    "FAULT",
    "SAFE_STOP",
    "EMERGENCY_STOP",
]

TransitionKey = tuple[EssState, EssState]

ALLOWED_STATE_TRANSITIONS: frozenset[TransitionKey] = frozenset(
    {
        ("IDLE", "STANDBY"),
        ("IDLE", "IN_PROGRESS"),
        ("IDLE", "CHARGING"),
        ("IDLE", "DISCHARGING"),
        ("STANDBY", "IN_PROGRESS"),
        ("STANDBY", "CHARGING"),
        ("STANDBY", "DISCHARGING"),
        ("STANDBY", "IDLE"),
        ("CHARGING", "IN_PROGRESS"),
        ("CHARGING", "STANDBY"),
        ("CHARGING", "DISCHARGING"),
        ("DISCHARGING", "IN_PROGRESS"),
        ("DISCHARGING", "STANDBY"),
        ("DISCHARGING", "CHARGING"),
        ("IN_PROGRESS", "STANDBY"),
        ("IN_PROGRESS", "CHARGING"),
        ("IN_PROGRESS", "DISCHARGING"),
        ("SAFE_STOP", "STANDBY"),
        ("SAFE_STOP", "IDLE"),
        ("FAULT", "STANDBY"),
        ("FAULT", "IDLE"),
    }
)


# 운전 모드에 대응되는 목표 상태를 계산한다.
def resolve_state_for_mode(mode: OperatingMode) -> EssState:
    if mode == "charge":
        return "CHARGING"
    if mode == "discharge":
        return "DISCHARGING"
    return "STANDBY"


# 문서의 전이표 기준으로 상태 전이가 허용되는지 검사한다.
def is_transition_allowed(current_state: EssState, next_state: EssState) -> bool:
    if current_state == next_state:
        return True
    if next_state in ("SAFE_STOP", "EMERGENCY_STOP"):
        return True
    return (current_state, next_state) in ALLOWED_STATE_TRANSITIONS


# 명령 처리 중 상태인지 검사한다.
def ensure_not_in_progress(current_state: EssState) -> None:
    if current_state == "IN_PROGRESS":
        raise ValueError("DEVICE_BUSY")


# 비상 정지 상태에서는 모든 일반 명령을 차단한다.
def ensure_emergency_inactive(emergency_stop: bool, current_state: EssState) -> None:
    if emergency_stop or current_state == "EMERGENCY_STOP":
        raise ValueError("EMERGENCY_STOP_ACTIVE")


# 로컬 fault 상태에서는 상태 전이를 차단한다.
def ensure_fault_inactive(local_fault: bool, current_state: EssState) -> None:
    if local_fault or current_state == "FAULT":
        raise ValueError("LOCAL_FAULT_ACTIVE")


# 이미 같은 상태로 운전 중이면 중복 명령으로 본다.
def ensure_not_already_in_state(
    *,
    current_state: EssState,
    current_mode: OperatingMode,
    requested_mode: OperatingMode,
) -> None:
    requested_state = resolve_state_for_mode(requested_mode)
    if current_state == requested_state and current_mode == requested_mode:
        raise ValueError("ALREADY_IN_STATE")


# 명령 기반 상태 전이가 가능한지 한 곳에서 검증한다.
def validate_mode_transition(
    *,
    current_state: EssState,
    current_mode: OperatingMode,
    requested_mode: OperatingMode,
    local_fault: bool,
    emergency_stop: bool,
) -> EssState:
    ensure_emergency_inactive(emergency_stop, current_state)
    ensure_fault_inactive(local_fault, current_state)
    ensure_not_in_progress(current_state)
    ensure_not_already_in_state(
        current_state=current_state,
        current_mode=current_mode,
        requested_mode=requested_mode,
    )
    requested_state = resolve_state_for_mode(requested_mode)
    if not is_transition_allowed(current_state, requested_state):
        raise ValueError("INVALID_STATE_TRANSITION")
    return requested_state


# 안전 규칙 평가 결과를 상태로 변환한다.
def resolve_safety_state(force_safe_stop: bool, local_fault: bool) -> EssState | None:
    if not force_safe_stop:
        return None
    if local_fault:
        return "FAULT"
    return "SAFE_STOP"


# 운전 모드와 fault 플래그를 기준으로 표시 상태를 다시 맞춘다.
def sync_state_with_mode(
    *,
    current_state: EssState,
    operating_mode: OperatingMode,
    local_fault: bool,
    emergency_stop: bool,
) -> EssState:
    if emergency_stop:
        return "EMERGENCY_STOP"
    if local_fault:
        return "FAULT"
    if current_state in ("SAFE_STOP", "FAULT", "EMERGENCY_STOP"):
        return current_state
    return resolve_state_for_mode(operating_mode)
