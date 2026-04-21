from __future__ import annotations

import unittest

from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from core.command_handler import CommandAck, CommandHandler
from core.ess import DeviceSpec, EssSimulator, SafetySpec


class PublisherStub:
    """기능 테스트에서 마지막 ACK만 보관하는 간단한 publisher다."""

    def __init__(self) -> None:
        self.last_ack: tuple[str, str, str, CommandAck] | None = None

    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack) -> None:
        self.last_ack = (plant_id, resource_type, device_id, ack)

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        return ack.model_dump_json(exclude_none=True)


class EssMqttFlowFunctionalTest(unittest.TestCase):
    def setUp(self) -> None:
        """실제 기능 흐름을 검증할 기본 앱 구성 요소를 만든다."""
        simulator = EssSimulator(
            device_spec=DeviceSpec(
                plant_id="PLANT-ALPHA",
                device_id="ess-01",
                resource_type="ess",
                publish_interval_sec=1.0,
                power_limit_kw=40.0,
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
        self.handler = CommandHandler(simulator)
        self.publisher = PublisherStub()
        self.subscriber = MqttCommandSubscriber(
            self.handler,
            self.publisher,
            "PLANT-ALPHA",
            "ess",
            "ess-01",
            "localhost",
            1883,
        )

    def test_command_changes_simulator_state_and_returns_ack(self) -> None:
        """정상 명령은 ACK뿐 아니라 simulator 상태도 함께 바꿔야 한다."""
        ack = self.subscriber.handle_message(
            "PLANT-ALPHA/ess/ess-01/command",
            '{"command_id":"cmd-100","command_type":"ess_mode","payload":{"mode":"charge","target_power_kw":15.0}}',
        )
        snapshot = self.handler.simulator.snapshot()

        self.assertEqual(ack.status, "accepted")
        self.assertEqual(snapshot["operating_mode"], "charge")
        self.assertEqual(snapshot["power_kw"], -15.0)

    def test_invalid_command_is_rejected_through_mqtt_callback(self) -> None:
        """잘못된 명령은 콜백 경로를 타더라도 rejected ACK로 끝나야 한다."""
        class Message:
            topic = "PLANT-ALPHA/ess/ess-01/command"
            payload = b'{"command_id":"cmd-101","command_type":"ess_mode","payload":{"mode":"invalid","target_power_kw":15.0}}'

        self.subscriber._on_message(None, None, Message())

        self.assertIsNotNone(self.publisher.last_ack)
        _, _, _, ack = self.publisher.last_ack
        self.assertEqual(ack.command_id, "cmd-101")
        self.assertEqual(ack.status, "rejected")


if __name__ == "__main__":
    unittest.main()
