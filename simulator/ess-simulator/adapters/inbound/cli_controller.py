from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

from core.command_handler import parse_simulator_command
from mqtt_contract import coerce_simulator_snapshot

if TYPE_CHECKING:
    from simulator_app import EssSimulatorApp


class CliExitRequested(Exception):
    pass


class CliController:
    _command_counter = itertools.count(1)

    def __init__(self, app: "EssSimulatorApp") -> None:
        self.app = app

    def handle_line(self, line: str) -> str | None:
        tokens = line.strip().split()
        if not tokens:
            return None

        command = tokens[0].lower()
        if command == "quit":
            raise CliExitRequested

        if command == "show":
            if len(tokens) == 1:
                return "\n".join(
                    f"{device_id}: {sim.snapshot()}"
                    for device_id, sim in sorted(self.app.simulators.items())
                )
            return str(self.app.simulators[tokens[1]].snapshot())

        if command == "mode":
            if len(tokens) < 3:
                raise ValueError("Usage: mode <device_id> <charge|discharge|standby> [target_power_kw]")
            device_id = tokens[1]
            payload: dict[str, Any] = {"mode": tokens[2].lower()}
            if len(tokens) >= 4:
                payload["target_power_kw"] = float(tokens[3])
            handler = self.app.command_handlers[device_id]
            ack = handler.handle_command(
                parse_simulator_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "ess_mode",
                    "payload": payload,
                }
                )
            )
            snapshot = coerce_simulator_snapshot(handler.simulator.snapshot())
            self.app.publisher.publish_ack(snapshot["plant_id"], snapshot["resource_type"], snapshot["device_id"], ack)
            return self.app.publisher.serialize_ack(ack)

        raise ValueError(f"Unknown command: {command}")

    @classmethod
    def _next_command_id(cls) -> str:
        return f"edge-cli-{next(cls._command_counter):04d}"
