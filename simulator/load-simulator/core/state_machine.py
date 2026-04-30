from __future__ import annotations

from enum import Enum


class LoadOperatingState(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SHED = "SHED"
    FAULT = "FAULT"
    DISABLED = "DISABLED"


TransitionKey = tuple[LoadOperatingState, LoadOperatingState]

ALLOWED_STATE_TRANSITIONS: frozenset[TransitionKey] = frozenset(
    {
        (LoadOperatingState.IDLE, LoadOperatingState.RUNNING),
        (LoadOperatingState.RUNNING, LoadOperatingState.SHED),
        (LoadOperatingState.SHED, LoadOperatingState.RUNNING),
        (LoadOperatingState.FAULT, LoadOperatingState.IDLE),
        (LoadOperatingState.FAULT, LoadOperatingState.RUNNING),
    }
)


# 활성 여부를 기준으로 장치의 초기 상태를 결정한다.
def resolve_initial_state(enabled: bool) -> LoadOperatingState:
    if not enabled:
        return LoadOperatingState.DISABLED
    return LoadOperatingState.IDLE


# 상태 전이가 허용되는지 규칙 테이블로 판정한다.
def is_transition_allowed(
    current_state: LoadOperatingState,
    next_state: LoadOperatingState,
) -> bool:
    if current_state == next_state:
        return True
    if current_state == LoadOperatingState.DISABLED:
        return next_state == LoadOperatingState.DISABLED
    if next_state == LoadOperatingState.FAULT:
        return True
    if next_state == LoadOperatingState.DISABLED:
        return True
    return (current_state, next_state) in ALLOWED_STATE_TRANSITIONS


# 허용되지 않은 전이를 예외로 막는다.
def validate_transition(
    current_state: LoadOperatingState,
    next_state: LoadOperatingState,
) -> LoadOperatingState:
    if not is_transition_allowed(current_state, next_state):
        raise ValueError(
            f"invalid transition: {current_state.value} -> {next_state.value}"
        )
    return next_state


# 장치 활성 상태와 제어 상태를 바탕으로 현재 운전 상태를 계산한다.
def resolve_runtime_state(
    *,
    enabled: bool,
    has_fault: bool,
    shed_ratio: float,
    has_measurement: bool,
) -> LoadOperatingState:
    if not enabled:
        return LoadOperatingState.DISABLED
    if has_fault:
        return LoadOperatingState.FAULT
    if shed_ratio > 0:
        return LoadOperatingState.SHED
    if has_measurement:
        return LoadOperatingState.RUNNING
    return LoadOperatingState.IDLE
