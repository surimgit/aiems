from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.load import LoadDevice, LoadFleet


@dataclass(slots=True)
class CommandAck:
    command_id: str
    status: str
    reason: str | None = None


@dataclass(slots=True)
class CommandResolution:
    accepted: bool
    device_id: str
    reason: str | None = None
    payload: dict[str, Any] | None = None


class LoadCommandHandler:
    # 장치 묶음을 기반으로 명령 처리기를 초기화한다.
    def __init__(self, fleet: LoadFleet) -> None:
        self.fleet = fleet

    # device_id로 대상 분전함을 찾아 반환한다.
    def resolve_device(self, device_id: str) -> LoadDevice:
        device = self.fleet.get(device_id)
        if device is None:
            raise ValueError(f"DEVICE_NOT_FOUND: {device_id}")
        return device

    # 명령 적용 전에 대상 장치와 기본 수용 가능 여부를 점검한다.
    def preview(self, *, device_id: str, payload: dict[str, Any]) -> CommandResolution:
        try:
            device = self.resolve_device(device_id)
        except ValueError as error:
            return CommandResolution(
                accepted=False,
                device_id=device_id,
                reason=str(error),
            )
        if not device.state.enabled:
            return CommandResolution(
                accepted=False,
                device_id=device_id,
                reason="DEVICE_DISABLED",
            )
        return CommandResolution(
            accepted=True,
            device_id=device_id,
            payload=payload,
        )

    # load_shed 명령을 검증하고 실제 분전함 상태에 반영한다.
    def handle_command(self, *, device_id: str, payload: dict[str, Any]) -> CommandAck:
        command_id = str(payload.get("command_id", "unknown"))
        resolution = self.preview(device_id=device_id, payload=payload)
        if not resolution.accepted:
            return CommandAck(
                command_id=command_id,
                status="rejected",
                reason=resolution.reason,
            )

        device = self.resolve_device(device_id)
        command_type = str(payload.get("command_type", "")).strip()
        if command_type != "load_shed":
            return CommandAck(
                command_id=command_id,
                status="rejected",
                reason=f"UNSUPPORTED_COMMAND_TYPE: {command_type or 'unknown'}",
            )

        payload_body = payload.get("payload", {})
        if not isinstance(payload_body, dict):
            return CommandAck(
                command_id=command_id,
                status="rejected",
                reason="INVALID_COMMAND_PAYLOAD",
            )

        reduction_ratio = payload_body.get("reduction_ratio")
        if not isinstance(reduction_ratio, (int, float)):
            return CommandAck(
                command_id=command_id,
                status="rejected",
                reason="INVALID_REDUCTION_RATIO",
            )
        if not 0.0 <= float(reduction_ratio) <= 1.0:
            return CommandAck(
                command_id=command_id,
                status="rejected",
                reason="INVALID_REDUCTION_RATIO",
            )

        device.set_shed_ratio(
            float(reduction_ratio),
            command_id=command_id,
        )
        return CommandAck(
            command_id=command_id,
            status="accepted",
        )
