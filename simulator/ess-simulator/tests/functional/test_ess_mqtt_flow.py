from __future__ import annotations

import unittest

from adapters.inbound.mqtt_subscriber import MqttCommandSubscriber
from core.command_handler import CommandAck, CommandHandler
from core.ess import DeviceSpec, EssSimulator, SafetySpec


class PublisherStub:
    def __init__(self) -> None:
        self.last_ack: tuple[str, str, str, CommandAck] | None = None

    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack) -> None:
        self.last_ack = (plant_id, resource_type, device_id, ack)

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        return ack.model_dump_json(exclude_none=True)


class EssMqttFlowFunctionalTest(unittest.TestCase):
    def setUp(self) -> None:
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
            {"ess-01": self.handler},
            self.publisher,
            "PLANT-ALPHA",
            "ess",
            "localhost",
            1883,
        )

    def test_command_changes_simulator_state_and_returns_ack(self) -> None:
        device_id, ack = self.subscriber.handle_message(
            "PLANT-ALPHA/ess/ess-01/command",
            '{"command_id":"cmd-100","command_type":"ess_mode","payload":{"mode":"charge","target_power_kw":15.0}}',
        )
        snapshot = self.handler.simulator.snapshot()

        self.assertEqual(device_id, "ess-01")
        self.assertEqual(ack.status, "accepted")
        self.assertEqual(snapshot["operating_mode"], "charge")
        self.assertEqual(snapshot["power_kw"], -15.0)
