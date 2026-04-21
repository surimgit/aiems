from __future__ import annotations

import itertools
from typing import Any

from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandHandler, parse_simulator_command
from mqtt_contract import coerce_simulator_snapshot


class CliExitRequested(Exception):
    pass


class CliController:
    _command_counter = itertools.count(1)

    def __init__(self, command_handler: CommandHandler, publisher: MqttPublisher) -> None:
        self.command_handler = command_handler
        self.publisher = publisher

    def handle_line(self, line: str) -> str | None:
        """CLI 입력 한 줄을 해석해 공통 command handler로 넘긴다."""

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
            payload: dict[str, Any] = {
                "mode": tokens[1].lower(),
            }
            if len(tokens) >= 3:
                payload["target_power_kw"] = float(tokens[2])
            ack = self.command_handler.handle_command(parse_simulator_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "ess_mode",
                    "payload": payload,
                }
            ))
            snapshot = coerce_simulator_snapshot(self.command_handler.simulator.snapshot())
            self.publisher.publish_ack(snapshot["plant_id"], snapshot["resource_type"], snapshot["device_id"], ack)
            return self.publisher.serialize_ack(ack)

        if command == "set-spec":
            if len(tokens) != 3:
                raise ValueError("Usage: set-spec <power_limit_kw|publish_interval_sec|capacity_kwh> <value>")
            ack = self.command_handler.handle_command(parse_simulator_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "update_device_spec",
                    "payload": {
                        tokens[1]: float(tokens[2]),
                    },
                }
            ))
            snapshot = coerce_simulator_snapshot(self.command_handler.simulator.snapshot())
            self.publisher.publish_ack(snapshot["plant_id"], snapshot["resource_type"], snapshot["device_id"], ack)
            return self.publisher.serialize_ack(ack)

        if command == "set-safety":
            if len(tokens) != 3:
                raise ValueError(
                    "Usage: set-safety <low_soc_threshold|high_soc_threshold|min_safe_soc_threshold|max_safe_soc_threshold|max_temperature_c> <value>"
                )
            ack = self.command_handler.handle_command(parse_simulator_command(
                {
                    "command_id": self._next_command_id(),
                    "command_type": "update_safety_spec",
                    "payload": {
                        tokens[1]: float(tokens[2]),
                    },
                }
            ))
            snapshot = coerce_simulator_snapshot(self.command_handler.simulator.snapshot())
            self.publisher.publish_ack(snapshot["plant_id"], snapshot["resource_type"], snapshot["device_id"], ack)
            return self.publisher.serialize_ack(ack)

        raise ValueError(f"Unknown command: {command}")

    @classmethod
    def _next_command_id(cls) -> str:
        """CLI에서 만든 명령에도 추적 가능한 command_id를 붙인다."""

        return f"edge-cli-{next(cls._command_counter):04d}"
