from __future__ import annotations

import json
import unittest

from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandAck
from core.load import load_fleet_from_config


class ClientSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.calls.append((topic, payload, qos))

    def connect(self, host: str, port: int, keepalive: int = 60) -> None:
        return None

    def loop_start(self) -> None:
        return None

    def loop_stop(self) -> None:
        return None

    def disconnect(self) -> None:
        return None


class MqttPublisherIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fleet = load_fleet_from_config("config/devices.yaml")
        self.device = self.fleet.get("load-01")

    def test_publish_telemetry_uses_contract_topic_and_payload(self) -> None:
        publisher = MqttPublisher("localhost", 1883)
        client = ClientSpy()
        publisher.client = client
        publisher.connected = True

        publisher.publish_telemetry(self.device)

        self.assertEqual(len(client.calls), 1)
        topic, payload, qos = client.calls[0]
        body = json.loads(payload)
        self.assertEqual(topic, "PLANT-ALPHA/load/load-01/telemetry")
        self.assertEqual(qos, 1)
        self.assertEqual(body["resource_type"], "load")
        self.assertEqual(body["data"]["status"]["panel_id"], "panel-01")

    def test_publish_ack_uses_ack_contract(self) -> None:
        publisher = MqttPublisher("localhost", 1883)
        client = ClientSpy()
        publisher.client = client
        publisher.connected = True

        publisher.publish_ack(
            "PLANT-ALPHA",
            "load",
            "load-01",
            CommandAck(command_id="cmd-003", status="accepted"),
        )

        self.assertEqual(len(client.calls), 1)
        topic, payload, qos = client.calls[0]
        body = json.loads(payload)
        self.assertEqual(topic, "PLANT-ALPHA/load/load-01/ack")
        self.assertEqual(qos, 1)
        self.assertEqual(body, {"command_id": "cmd-003", "status": "accepted"})

    def test_publish_heartbeat_uses_heartbeat_topic_and_payload(self) -> None:
        publisher = MqttPublisher("localhost", 1883)
        client = ClientSpy()
        publisher.client = client
        publisher.connected = True

        publisher.publish_heartbeat("PLANT-ALPHA", "load", "load-01")

        self.assertEqual(len(client.calls), 1)
        topic, payload, qos = client.calls[0]
        body = json.loads(payload)
        self.assertEqual(topic, "PLANT-ALPHA/heartbeat")
        self.assertEqual(qos, 1)
        self.assertEqual(body["plant_id"], "PLANT-ALPHA")
        self.assertEqual(body["resource_type"], "load")
        self.assertEqual(body["device_id"], "load-01")


if __name__ == "__main__":
    unittest.main()
