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


def resolve_initial_state(enabled: bool) -> LoadOperatingState:
    if not enabled:
        return LoadOperatingState.DISABLED
    return LoadOperatingState.IDLE


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


def validate_transition(
    current_state: LoadOperatingState,
    next_state: LoadOperatingState,
) -> LoadOperatingState:
    if not is_transition_allowed(current_state, next_state):
        raise ValueError(
            f"invalid transition: {current_state.value} -> {next_state.value}"
        )
    return next_state


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
