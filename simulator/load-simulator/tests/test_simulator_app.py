from __future__ import annotations

import json
import unittest
from pathlib import Path

from runtime_config import load_config
from simulator_app import LoadSimulatorApp


BASE_DIR = Path(__file__).resolve().parents[1]


class PublisherSpy:
    def __init__(self) -> None:
        self.telemetry_inputs: list[str] = []
        self.heartbeat_inputs: list[tuple[str, str, str]] = []
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    @staticmethod
    def serialize_telemetry(device) -> str:
        return json.dumps({"device_id": device.device_id, "power_kw": device.measurement.p_kw})

    @staticmethod
    def serialize_heartbeat(site_id: str, device_id: str) -> str:
        return json.dumps({"site_id": site_id, "device_id": device_id, "status": "alive"})

    def publish_telemetry(self, device) -> None:
        self.telemetry_inputs.append(device.device_id)

    def publish_heartbeat(self, site_id: str, resource_type: str, device_id: str) -> None:
        self.heartbeat_inputs.append((site_id, resource_type, device_id))


class SubscriberSpy:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


class LoadSimulatorAppUnitTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        config = load_config(
            BASE_DIR / "config" / "devices.yaml",
            BASE_DIR / "config" / "scenario.yaml",
        )
        self.app = LoadSimulatorApp(config)
        self.app.publisher = PublisherSpy()
        self.app.mqtt_subscriber = SubscriberSpy()

    def test_run_publish_cycle_builds_and_publishes_messages_for_enabled_devices(self) -> None:
        batches = self.app.run_publish_cycle()

        self.assertEqual(len(batches), 2)
        self.assertEqual(len(self.app.publisher.telemetry_inputs), 2)
        self.assertEqual(len(self.app.publisher.heartbeat_inputs), 2)
        self.assertEqual(self.app.publisher.heartbeat_inputs[1], ("PLANT-ALPHA", "load", "load-02"))

    async def test_run_starts_and_stops_runtime_dependencies(self) -> None:
        await self.app.run(max_cycles=1)

        self.assertTrue(self.app.publisher.started)
        self.assertTrue(self.app.publisher.stopped)
        self.assertTrue(self.app.mqtt_subscriber.started)
        self.assertTrue(self.app.mqtt_subscriber.stopped)


if __name__ == "__main__":
    unittest.main()
