from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from .ess import EssSimulator


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


class CommandAck(BaseModel):
    command_id: str
    status: Literal["accepted", "rejected"]
    reason: str | None = None
    applied: dict[str, Any] | None = None


class EssModeCommand(BaseModel):
    command_id: str
    command_type: Literal["ess_mode"]
    payload: EssModePayload


class UpdateDeviceSpecCommand(BaseModel):
    command_id: str
    command_type: Literal["update_device_spec"]
    payload: UpdateDeviceSpecPayload


class UpdateSafetySpecCommand(BaseModel):
    command_id: str
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
        """Apply a validated simulator command and return the result."""

        try:
            if command.command_type == "ess_mode":
                self.simulator.set_mode(command.payload.mode, command.payload.target_power_kw)
                return CommandAck(
                    command_id=command.command_id,
                    status="accepted",
                    applied={
                        "mode": command.payload.mode,
                        "target_power_kw": command.payload.target_power_kw,
                    },
                )

            if command.command_type == "update_device_spec":
                applied = self.simulator.update_device_spec(
                    power_limit_kw=command.payload.power_limit_kw,
                    publish_interval_sec=command.payload.publish_interval_sec,
                )
                return CommandAck(
                    command_id=command.command_id,
                    status="accepted",
                    applied=applied,
                )

            applied = self.simulator.update_safety_spec(
                low_soc_threshold=command.payload.low_soc_threshold,
                high_soc_threshold=command.payload.high_soc_threshold,
                min_safe_soc_threshold=command.payload.min_safe_soc_threshold,
                max_safe_soc_threshold=command.payload.max_safe_soc_threshold,
                max_temperature_c=command.payload.max_temperature_c,
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
