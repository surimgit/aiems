from __future__ import annotations

import unittest

from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from core.command_handler import CommandAck, LoadCommandHandler
from core.load import load_fleet_from_config


class PublisherSpy:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, CommandAck]] = []

    def publish_ack(self, site_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        self.calls.append((site_id, resource_type, device_id, ack))

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        return f"{ack.command_id}:{ack.status}"


class MessageStub:
    def __init__(self, topic: str, payload: str) -> None:
        self.topic = topic
        self.payload = payload.encode("utf-8")


class MqttSubscriberIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fleet = load_fleet_from_config("config/devices.yaml")

    def test_handle_message_routes_valid_command_by_device_id(self) -> None:
        subscriber = MqttCommandSubscriber(
            LoadCommandHandler(self.fleet),
            PublisherSpy(),
            "PLANT-ALPHA",
            "load",
            "localhost",
            1883,
        )

        device_id, ack = subscriber.handle_message(
            "PLANT-ALPHA/load/load-02/command",
            '{"command_id":"cmd-001","command_type":"load_shed","payload":{"reduction_ratio":0.3}}',
        )

        self.assertEqual(device_id, "load-02")
        self.assertEqual(ack.status, "accepted")

    def test_on_message_publishes_rejected_ack_for_invalid_payload(self) -> None:
        publisher = PublisherSpy()
        subscriber = MqttCommandSubscriber(
            LoadCommandHandler(self.fleet),
            publisher,
            "PLANT-ALPHA",
            "load",
            "localhost",
            1883,
        )

        subscriber._on_message(
            None,
            None,
            MessageStub(
                "PLANT-ALPHA/load/load-01/command",
                '{"command_id":"cmd-002","command_type":"load_shed","payload":{"reduction_ratio":1.5}}',
            ),
        )

        self.assertEqual(len(publisher.calls), 1)
        site_id, resource_type, device_id, ack = publisher.calls[0]
        self.assertEqual((site_id, resource_type, device_id), ("PLANT-ALPHA", "load", "load-01"))
        self.assertEqual(ack.command_id, "cmd-002")
        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "INVALID_REDUCTION_RATIO")


if __name__ == "__main__":
    unittest.main()
