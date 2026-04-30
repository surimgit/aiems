from __future__ import annotations

import unittest

from simulator_app import EssSimulatorApp


class SimulatorStub:
    def __init__(self, device_id: str, power_kw: float) -> None:
        self.device_id = device_id
        self.power_kw = power_kw
        self.tick_count = 0
        self.device_spec = type("Spec", (), {"publish_interval_sec": 0.1})()

    def tick(self) -> dict[str, object]:
        self.tick_count += 1
        return {
            "plant_id": "PLANT-ALPHA",
            "device_id": self.device_id,
            "resource_type": "ess",
            "publish_interval_sec": 0.1,
            "soc": 67.3,
            "power_kw": self.power_kw,
            "operating_mode": "discharge" if self.power_kw > 0 else "charge",
            "accumulated_energy_kwh": 820.0,
        }


class PublisherSpy:
    def __init__(self) -> None:
        self.telemetry_inputs: list[dict[str, object]] = []
        self.heartbeat_inputs: list[tuple[str, str, str]] = []

    @staticmethod
    def serialize_telemetry(snapshot: dict[str, object]) -> str:
        return f"telemetry:{snapshot['device_id']}:{snapshot['power_kw']}"

    @staticmethod
    def serialize_heartbeat(plant_id: str, resource_type: str, device_id: str) -> str:
        return f"heartbeat:{plant_id}:{resource_type}:{device_id}"

    def publish_telemetry(self, snapshot: dict[str, object]) -> None:
        self.telemetry_inputs.append(snapshot)

    def publish_heartbeat(self, plant_id: str, resource_type: str, device_id: str) -> None:
        self.heartbeat_inputs.append((plant_id, resource_type, device_id))


class EssSimulatorAppUnitTest(unittest.TestCase):
    def test_run_publish_cycle_builds_and_publishes_messages_for_all_devices(self) -> None:
        app = EssSimulatorApp.__new__(EssSimulatorApp)
        app.simulators = {
            "ess-01": SimulatorStub("ess-01", 30.0),
            "ess-02": SimulatorStub("ess-02", -12.0),
        }
        app.publisher = PublisherSpy()

        batches = app.run_publish_cycle()

        self.assertEqual(len(batches), 2)
        self.assertEqual(app.simulators["ess-01"].tick_count, 1)
        self.assertEqual(app.simulators["ess-02"].tick_count, 1)
        self.assertEqual(len(app.publisher.telemetry_inputs), 2)
        self.assertEqual(len(app.publisher.heartbeat_inputs), 2)
        self.assertEqual(
            app.publisher.heartbeat_inputs[1],
            ("PLANT-ALPHA", "ess", "ess-02"),
        )


if __name__ == "__main__":
    unittest.main()
