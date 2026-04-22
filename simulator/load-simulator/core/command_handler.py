from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.load import LoadDevice, LoadFleet


@dataclass(slots=True)
class CommandResolution:
    accepted: bool
    device_id: str
    reason: str | None = None
    payload: dict[str, Any] | None = None


class LoadCommandHandler:
    """Task 1 only defines the per-panel routing boundary.

    Real load shedding execution belongs to the next Jira task.
    """

    def __init__(self, fleet: LoadFleet) -> None:
        self.fleet = fleet

    def resolve_device(self, device_id: str) -> LoadDevice:
        device = self.fleet.get(device_id)
        if device is None:
            raise ValueError(f"DEVICE_NOT_FOUND: {device_id}")
        return device

    def preview(self, *, device_id: str, payload: dict[str, Any]) -> CommandResolution:
        try:
            self.resolve_device(device_id)
        except ValueError as error:
            return CommandResolution(
                accepted=False,
                device_id=device_id,
                reason=str(error),
            )
        return CommandResolution(
            accepted=True,
            device_id=device_id,
            payload=payload,
        )
