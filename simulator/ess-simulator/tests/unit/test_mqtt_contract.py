from __future__ import annotations

from datetime import datetime, timezone
import unittest

from mqtt_contract import (
    SimulatorSnapshot,
    build_heartbeat_message,
    build_heartbeat_topic,
    build_topic,
    parse_ess_command,
    parse_heartbeat_topic,
    parse_topic,
    snapshot_to_telemetry,
    to_simulator_command,
)


class MqttContractUnitTest(unittest.TestCase):
    def test_build_and_parse_topic(self) -> None:
        topic = build_topic("PLANT-ALPHA", "ess", "ess-01", "telemetry")
        parsed = parse_topic(topic)
        self.assertEqual(parsed.device_id, "ess-01")
        self.assertEqual(parsed.message_type, "telemetry")

    def test_build_and_parse_heartbeat_topic(self) -> None:
        topic = build_heartbeat_topic("PLANT-ALPHA")
        parsed = parse_heartbeat_topic(topic)
        self.assertEqual(parsed.message_type, "heartbeat")

    def test_build_heartbeat_message_uses_minimum_contract_shape(self) -> None:
        message = build_heartbeat_message(
            "PLANT-ALPHA",
            "ess",
            "ess-01",
            timestamp=datetime(2026, 4, 14, 7, 50, tzinfo=timezone.utc),
        )
        self.assertEqual(message.timestamp, "2026-04-14T07:50:00Z")

    def test_parse_ess_command_and_convert_to_simulator_command(self) -> None:
        payload = """
        {
          "command_id": "cmd-042",
          "command_type": "ess_mode",
          "payload": {
            "mode": "charge",
            "target_power_kw": 30.0
          }
        }
        """
        _, message = parse_ess_command("PLANT-ALPHA/ess/ess-02/command", payload, "PLANT-ALPHA")
        command = to_simulator_command(message)
        self.assertEqual(command.command_id, "cmd-042")
        self.assertEqual(command.payload.mode, "charge")

    def test_parse_ess_command_rejects_other_plant(self) -> None:
        with self.assertRaises(ValueError):
            parse_ess_command(
                "PLANT-BETA/ess/ess-02/command",
                '{"command_id":"cmd-1","command_type":"ess_mode","payload":{"mode":"standby"}}',
                "PLANT-ALPHA",
            )

    def test_snapshot_to_telemetry_uses_contract_shape(self) -> None:
        snapshot: SimulatorSnapshot = {
            "plant_id": "PLANT-ALPHA",
            "device_id": "ess-01",
            "resource_type": "ess",
            "soc": 67.3,
            "power_kw": 30.0,
            "operating_mode": "discharge",
            "accumulated_energy_kwh": 820.0,
        }
        message = snapshot_to_telemetry(snapshot, timestamp=datetime(2026, 4, 14, 7, 50, tzinfo=timezone.utc))
        self.assertEqual(message.data.status.SOC, 67.3)
