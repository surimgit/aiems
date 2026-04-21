from __future__ import annotations

import unittest

from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from core.command_handler import CommandAck, CommandHandler
from core.ess import DeviceSpec, EssSimulator, SafetySpec


class PublisherSpy:
    """Subscriber가 어떤 ACK를 발행했는지 기록하는 테스트 더블이다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str, CommandAck]] = []

    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        self.calls.append((plant_id, resource_type, device_id, ack))

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        return ack.model_dump_json(exclude_none=True)


class MessageStub:
    """실제 MQTTMessage 대신 쓰는 최소 메시지 객체다."""

    def __init__(self, topic: str, payload: str) -> None:
        self.topic = topic
        self.payload = payload.encode("utf-8")


def build_handler() -> CommandHandler:
    """테스트마다 재사용할 기본 ESS handler를 만든다."""
    simulator = EssSimulator(
        device_spec=DeviceSpec(
            plant_id="PLANT-ALPHA",
            device_id="ess-01",
            resource_type="ess",
            publish_interval_sec=1.0,
            power_limit_kw=50.0,
            capacity_kwh=500.0,
        ),
        safety_spec=SafetySpec(
            low_soc_threshold=20.0,
            high_soc_threshold=80.0,
            min_safe_soc_threshold=5.0,
            max_safe_soc_threshold=95.0,
            max_temperature_c=60.0,
        ),
        initial_soc=50.0,
    )
    return CommandHandler(simulator)


class MqttSubscriberIntegrationTest(unittest.TestCase):
    def test_handle_message_routes_valid_command(self) -> None:
        """정상 command는 handler까지 전달돼 accepted ACK를 만들어야 한다."""
        subscriber = MqttCommandSubscriber(
            build_handler(),
            PublisherSpy(),
            "PLANT-ALPHA",
            "ess",
            "ess-01",
            "localhost",
            1883,
        )

        ack = subscriber.handle_message(
            "PLANT-ALPHA/ess/ess-01/command",
            '{"command_id":"cmd-001","command_type":"ess_mode","payload":{"mode":"discharge","target_power_kw":20.0}}',
        )

        self.assertEqual(ack.status, "accepted")
        self.assertEqual(ack.applied, {"mode": "discharge", "target_power_kw": 20.0})

    def test_on_message_publishes_rejected_ack_for_invalid_payload(self) -> None:
        """잘못된 payload는 MQTT 콜백 단계에서 rejected ACK로 바뀌어야 한다."""
        publisher = PublisherSpy()
        subscriber = MqttCommandSubscriber(
            build_handler(),
            publisher,
            "PLANT-ALPHA",
            "ess",
            "ess-01",
            "localhost",
            1883,
        )

        subscriber._on_message(
            None,
            None,
            MessageStub(
                "PLANT-ALPHA/ess/ess-01/command",
                '{"command_id":"cmd-002","command_type":"ess_mode","payload":{"mode":"invalid","target_power_kw":20.0}}',
            ),
        )

        self.assertEqual(len(publisher.calls), 1)
        plant_id, resource_type, device_id, ack = publisher.calls[0]
        self.assertEqual((plant_id, resource_type, device_id), ("PLANT-ALPHA", "ess", "ess-01"))
        self.assertEqual(ack.command_id, "cmd-002")
        self.assertEqual(ack.status, "rejected")


if __name__ == "__main__":
    unittest.main()
