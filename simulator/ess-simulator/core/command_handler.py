from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from .ess import EssSimulator
from .safety_guards import (
    ensure_command_not_expired,
    ensure_comms_healthy,
    ensure_emergency_not_active,
    ensure_interlock_clear,
    ensure_local_safety_clear,
)


class EssModePayload(BaseModel):
    mode: Literal["charge", "discharge", "standby"]
    target_power_kw: float | None = Field(default=None, ge=0)


class UpdateDeviceSpecPayload(BaseModel):
    power_limit_kw: float | None = Field(default=None, gt=0)
    publish_interval_sec: float | None = Field(default=None, gt=0)
    capacity_kwh: float | None = Field(default=None, gt=0)


class UpdateSafetySpecPayload(BaseModel):
    low_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    high_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    min_safe_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    max_safe_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    max_temperature_c: float | None = Field(default=None, gt=0)


class CommandAck(BaseModel):
    command_id: str
    status: Literal["accepted", "rejected"]
    reason: str | None = None
    applied: dict[str, Any] | None = None


class CommandMeta(BaseModel):
    command_id: str
    issued_at: datetime | None = None
    expires_in_sec: float | None = Field(default=None, gt=0)
    force: bool = False
    source: str | None = None


class EssModeCommand(CommandMeta):
    command_type: Literal["ess_mode"]
    payload: EssModePayload


class UpdateDeviceSpecCommand(CommandMeta):
    command_type: Literal["update_device_spec"]
    payload: UpdateDeviceSpecPayload


class UpdateSafetySpecCommand(CommandMeta):
    command_type: Literal["update_safety_spec"]
    payload: UpdateSafetySpecPayload


SimulatorCommand = Annotated[
    EssModeCommand | UpdateDeviceSpecCommand | UpdateSafetySpecCommand,
    Field(discriminator="command_type"),
]

SIMULATOR_COMMAND_ADAPTER = TypeAdapter(SimulatorCommand)


def parse_simulator_command(raw_command: dict[str, Any]) -> SimulatorCommand:
    """Validate an inbound command against the simulator command models."""

    return SIMULATOR_COMMAND_ADAPTER.validate_python(raw_command)


class CommandHandler:
    def __init__(self, simulator: EssSimulator) -> None:
        self.simulator = simulator

    def handle_command(self, command: SimulatorCommand) -> CommandAck:
        """검증된 명령을 처리 흐름에 맞게 조립하고 ACK를 반환한다."""

        try:
            applied = self._dispatch_command(command)
            return self._build_accepted_ack(command.command_id, applied)
        except Exception as exc:
            return self._build_rejected_ack(command.command_id, exc)

    def _dispatch_command(self, command: SimulatorCommand) -> dict[str, Any] | None:
        """명령 타입별 순수 처리 함수를 선택하고 결과만 돌려준다."""

        if command.command_type == "ess_mode":
            return self._apply_ess_mode(command)
        if command.command_type == "update_device_spec":
            return self._apply_device_spec(command)
        return self._apply_safety_spec(command)

    def _apply_ess_mode(self, command: EssModeCommand) -> dict[str, Any]:
        """ESS 모드 명령을 실행하고 문서 기준 적용값을 반환한다."""

        self._ensure_mode_command_allowed(command)
        self.simulator.set_mode(command.payload.mode, command.payload.target_power_kw)
        return {
            "mode": command.payload.mode,
            "target_power_kw": command.payload.target_power_kw,
        }

    def _ensure_mode_command_allowed(self, command: EssModeCommand) -> None:
        """운전 명령에만 적용되는 안전 차단 조건을 순서대로 검사한다."""

        now = datetime.now(timezone.utc)
        ensure_emergency_not_active(
            emergency_stop=self.simulator.status.emergency_stop,
            current_state=self.simulator.status.state,
        )
        ensure_interlock_clear(interlock_active=self.simulator.status.interlock_active)
        ensure_comms_healthy(comms_healthy=self.simulator.status.comms_healthy)
        ensure_command_not_expired(
            issued_at=command.issued_at,
            expires_in_sec=command.expires_in_sec,
            current_time=now,
        )
        ensure_local_safety_clear(local_fault=self.simulator.status.local_fault)

    def _apply_device_spec(self, command: UpdateDeviceSpecCommand) -> dict[str, float]:
        """장비 스펙 변경을 simulator에 위임하고 반영값을 그대로 돌려준다."""

        return self.simulator.update_device_spec(
            power_limit_kw=command.payload.power_limit_kw,
            publish_interval_sec=command.payload.publish_interval_sec,
            capacity_kwh=command.payload.capacity_kwh,
        )

    def _apply_safety_spec(self, command: UpdateSafetySpecCommand) -> dict[str, float]:
        """안전 스펙 변경을 simulator에 위임하고 반영값을 그대로 돌려준다."""

        return self.simulator.update_safety_spec(
            low_soc_threshold=command.payload.low_soc_threshold,
            high_soc_threshold=command.payload.high_soc_threshold,
            min_safe_soc_threshold=command.payload.min_safe_soc_threshold,
            max_safe_soc_threshold=command.payload.max_safe_soc_threshold,
            max_temperature_c=command.payload.max_temperature_c,
        )

    @staticmethod
    def _build_accepted_ack(command_id: str, applied: dict[str, Any] | None = None) -> CommandAck:
        """성공 시 문서 규격에 맞는 accepted ACK를 만든다."""

        return CommandAck(
            command_id=command_id,
            status="accepted",
            applied=applied,
        )

    @staticmethod
    def _build_rejected_ack(command_id: str, exc: Exception) -> CommandAck:
        """실패 사유를 reason code 중심으로 정규화해 rejected ACK를 만든다."""

        return CommandAck(
            command_id=command_id,
            status="rejected",
            reason=CommandHandler._normalize_reason(exc),
        )

    @staticmethod
    def _normalize_reason(exc: Exception) -> str:
        """설계문서의 reason code 체계에 맞춰 예외를 표준화한다."""

        reason = str(exc).strip() or exc.__class__.__name__
        known_reason_codes = {
            "INTERLOCK_VIOLATION",
            "EMERGENCY_STOP_ACTIVE",
            "DEVICE_BUSY",
            "ALREADY_IN_STATE",
            "COMMAND_EXPIRED",
            "LOCAL_SAFETY_BLOCKED",
            "INVALID_STATE_TRANSITION",
            "NO_DEVICE_ACK",
        }
        if reason in known_reason_codes:
            return reason
        return reason
