from __future__ import annotations

import itertools

from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandHandler


class CliExitRequested(Exception):
    pass


class CliController:
    _command_counter = itertools.count(1)

    def __init__(self, command_handler: CommandHandler, publisher: MqttPublisher) -> None:
        self.command_handler = command_handler
        self.publisher = publisher

    def handle_line(self, line: str) -> str | None:
        tokens = line.strip().split()
        if not tokens:
            return None

        command = tokens[0].lower()

        if command == "quit":
            raise CliExitRequested

        if command == "show":
            return str(self.command_handler.simulator.snapshot())

        if command == "mode":
            if len(tokens) < 2:
                raise ValueError("Usage: mode <charge|discharge|standby> [target_power_kw]")
            payload = {
                "mode": tokens[1].lower(),
            }
            if len(tokens) >= 3:
                payload["target_power_kw"] = float(tokens[2])
            ack = self.command_handler.handle_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "ess_mode",
                    "payload": payload,
                }
            )
            snapshot = self.command_handler.simulator.snapshot()
            self.publisher.publish_ack(snapshot["plant_id"], snapshot["device_id"], ack)
            return self.publisher.serialize_ack(ack)

        if command == "set-spec":
            if len(tokens) != 3:
                raise ValueError("Usage: set-spec <power_limit_kw|publish_interval_sec> <value>")
            ack = self.command_handler.handle_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "update_device_spec",
                    "payload": {
                        tokens[1]: float(tokens[2]),
                    },
                }
            )
            snapshot = self.command_handler.simulator.snapshot()
            self.publisher.publish_ack(snapshot["plant_id"], snapshot["device_id"], ack)
            return self.publisher.serialize_ack(ack)

        if command == "set-safety":
            if len(tokens) != 3:
                raise ValueError(
                    "Usage: set-safety <low_soc_threshold|high_soc_threshold|min_safe_soc_threshold|max_safe_soc_threshold|max_temperature_c> <value>"
                )
            ack = self.command_handler.handle_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "update_safety_spec",
                    "payload": {
                        tokens[1]: float(tokens[2]),
                    },
                }
            )
            snapshot = self.command_handler.simulator.snapshot()
            self.publisher.publish_ack(snapshot["plant_id"], snapshot["device_id"], ack)
            return self.publisher.serialize_ack(ack)

        raise ValueError(f"Unknown command: {command}")

    @classmethod
    def _next_command_id(cls) -> str:
        return f"edge-cli-{next(cls._command_counter):04d}"
