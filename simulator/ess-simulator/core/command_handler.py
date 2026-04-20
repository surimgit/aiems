from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .ess import EssSimulator, OperatingMode


class EssModePayload(BaseModel):
    mode: Literal["charge", "discharge", "standby"]
    target_power_kw: float | None = Field(default=None, ge=0)


class UpdateDeviceSpecPayload(BaseModel):
    power_limit_kw: float | None = Field(default=None, gt=0)
    publish_interval_sec: float | None = Field(default=None, gt=0)


class UpdateSafetySpecPayload(BaseModel):
    low_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    high_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    min_safe_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    max_safe_soc_threshold: float | None = Field(default=None, ge=0, le=100)
    max_temperature_c: float | None = Field(default=None, gt=0)


class CommandEnvelope(BaseModel):
    command_id: str
    command_type: Literal["ess_mode", "update_device_spec", "update_safety_spec"]
    payload: dict[str, Any]


class CommandAck(BaseModel):
    command_id: str
    status: Literal["accepted", "rejected"]
    reason: str | None = None
    applied: dict[str, Any] | None = None


class CommandHandler:
    def __init__(self, simulator: EssSimulator) -> None:
        self.simulator = simulator

    def handle_command(self, raw_command: dict[str, Any]) -> CommandAck:
        command = CommandEnvelope.model_validate(raw_command)

        try:
            if command.command_type == "ess_mode":
                payload = EssModePayload.model_validate(command.payload)
                self.simulator.set_mode(payload.mode, payload.target_power_kw)
                return CommandAck(
                    command_id=command.command_id,
                    status="accepted",
                    applied={
                        "mode": payload.mode,
                        "target_power_kw": payload.target_power_kw,
                    },
                )

            if command.command_type == "update_device_spec":
                payload = UpdateDeviceSpecPayload.model_validate(command.payload)
                applied = self.simulator.update_device_spec(
                    power_limit_kw=payload.power_limit_kw,
                    publish_interval_sec=payload.publish_interval_sec,
                )
                return CommandAck(
                    command_id=command.command_id,
                    status="accepted",
                    applied=applied,
                )

            payload = UpdateSafetySpecPayload.model_validate(command.payload)
            applied = self.simulator.update_safety_spec(
                low_soc_threshold=payload.low_soc_threshold,
                high_soc_threshold=payload.high_soc_threshold,
                min_safe_soc_threshold=payload.min_safe_soc_threshold,
                max_safe_soc_threshold=payload.max_safe_soc_threshold,
                max_temperature_c=payload.max_temperature_c,
            )
            return CommandAck(
                command_id=command.command_id,
                status="accepted",
                applied=applied,
            )
        except Exception as exc:
            return CommandAck(
                command_id=command.command_id,
                status="rejected",
                reason=str(exc),
            )
