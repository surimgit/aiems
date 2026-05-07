from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .state_machine import EssState


def ensure_command_not_expired(
    *,
    issued_at: datetime | None,
    expires_in_sec: float | None,
    current_time: datetime,
) -> None:
    """유효 시간이 지정된 명령만 만료 여부를 검사한다."""

    if expires_in_sec is None or issued_at is None:
        return
    if issued_at.tzinfo is None:
        issued_at = issued_at.replace(tzinfo=timezone.utc)
    if current_time > issued_at + timedelta(seconds=expires_in_sec):
        raise ValueError("COMMAND_EXPIRED")


def ensure_interlock_clear(*, interlock_active: bool) -> None:
    """인터락이 걸린 상태에서는 운전 명령을 차단한다."""

    if interlock_active:
        raise ValueError("INTERLOCK_VIOLATION")


def ensure_comms_healthy(*, comms_healthy: bool) -> None:
    """통신 장애 상태에서는 명령 실행을 차단한다."""

    if not comms_healthy:
        raise ValueError("NO_DEVICE_ACK")


def ensure_emergency_not_active(*, emergency_stop: bool, current_state: EssState) -> None:
    """비상 정지 상태에서는 추가 운전 명령을 차단한다."""

    if emergency_stop or current_state == "EMERGENCY_STOP":
        raise ValueError("EMERGENCY_STOP_ACTIVE")


def ensure_local_safety_clear(*, local_fault: bool) -> None:
    """로컬 안전 차단 또는 fault 상태에서는 운전 명령을 차단한다."""

    if local_fault:
        raise ValueError("LOCAL_SAFETY_BLOCKED")
