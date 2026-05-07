from __future__ import annotations

import unittest

from core.load import load_fleet_from_config
from mqtt_contract import (
    RESOURCE_TYPE,
    ack_to_payload,
    build_heartbeat_topic,
    build_topic,
    parse_load_command,
    parse_topic,
    snapshot_to_telemetry,
)


class MqttContractUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fleet = load_fleet_from_config("config/devices.yaml")
        self.device = self.fleet.get("load-01")

    def test_build_topic_uses_load_contract(self) -> None:
        self.assertEqual(
            build_topic("PLANT-ALPHA", RESOURCE_TYPE, "load-01", "telemetry"),
            "PLANT-ALPHA/load/load-01/telemetry",
        )

    def test_parse_topic_extracts_all_parts(self) -> None:
        topic = parse_topic("PLANT-ALPHA/load/load-02/command")
        self.assertEqual(topic.site_id, "PLANT-ALPHA")
        self.assertEqual(topic.device_id, "load-02")
        self.assertEqual(topic.message_type, "command")

    def test_parse_load_command_validates_payload(self) -> None:
        topic, command = parse_load_command(
            "PLANT-ALPHA/load/load-01/command",
            '{"command_id":"cmd-001","command_type":"load_shed","payload":{"reduction_ratio":0.3}}',
            "PLANT-ALPHA",
        )
        self.assertEqual(topic.device_id, "load-01")
        self.assertEqual(command.command_id, "cmd-001")
        self.assertEqual(command.payload["reduction_ratio"], 0.3)

    def test_snapshot_to_telemetry_uses_device_measurement(self) -> None:
        payload = snapshot_to_telemetry(self.device)
        self.assertEqual(payload["resource_type"], "load")
        self.assertEqual(payload["device_id"], "load-01")
        self.assertEqual(payload["data"]["status"]["panel_id"], "panel-01")

    def test_ack_payload_omits_reason_when_not_present(self) -> None:
        payload = ack_to_payload(type("Ack", (), {"command_id": "cmd-003", "status": "accepted", "reason": None})())
        self.assertEqual(payload, {"command_id": "cmd-003", "status": "accepted"})

    def test_build_heartbeat_topic_uses_site_only(self) -> None:
        self.assertEqual(build_heartbeat_topic("PLANT-ALPHA"), "PLANT-ALPHA/heartbeat")


if __name__ == "__main__":
    unittest.main()
