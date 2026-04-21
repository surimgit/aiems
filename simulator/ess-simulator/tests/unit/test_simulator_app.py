from __future__ import annotations

import unittest

from simulator_app import EssSimulatorApp


class SimulatorStub:
    def __init__(self) -> None:
        self.tick_count = 0

    # 주기 발행 직전의 장치 상태를 고정된 snapshot으로 반환한다.
    def tick(self) -> dict[str, object]:
        self.tick_count += 1
        return {
            "plant_id": "PLANT-ALPHA",
            "device_id": "ess-01",
            "resource_type": "ess",
            "publish_interval_sec": 0.1,
            "soc": 67.3,
            "power_kw": 30.0,
            "operating_mode": "discharge",
            "accumulated_energy_kwh": 820.0,
        }


class PublisherSpy:
    def __init__(self) -> None:
        self.telemetry_inputs: list[dict[str, object]] = []
        self.heartbeat_inputs: list[tuple[str, str, str]] = []

    # telemetry snapshot을 JSON 문자열로 직렬화했다고 가정한다.
    @staticmethod
    def serialize_telemetry(snapshot: dict[str, object]) -> str:
        return f"telemetry:{snapshot['device_id']}:{snapshot['power_kw']}"

    # heartbeat payload를 JSON 문자열로 직렬화했다고 가정한다.
    @staticmethod
    def serialize_heartbeat(plant_id: str, resource_type: str, device_id: str) -> str:
        return f"heartbeat:{plant_id}:{resource_type}:{device_id}"

    # telemetry 발행 요청을 추적해 발행 사이클 검증에 사용한다.
    def publish_telemetry(self, snapshot: dict[str, object]) -> None:
        self.telemetry_inputs.append(snapshot)

    # heartbeat 발행 요청을 추적해 topic 인자 조립을 검증한다.
    def publish_heartbeat(self, plant_id: str, resource_type: str, device_id: str) -> None:
        self.heartbeat_inputs.append((plant_id, resource_type, device_id))


class EssSimulatorAppUnitTest(unittest.TestCase):
    # 조립된 주기 발행 사이클이 telemetry와 heartbeat를 함께 준비하고 발행해야 한다.
    def test_run_publish_cycle_builds_and_publishes_messages(self) -> None:
        app = EssSimulatorApp.__new__(EssSimulatorApp)
        app.simulator = SimulatorStub()
        app.publisher = PublisherSpy()

        batch = app.run_publish_cycle()

        self.assertEqual(app.simulator.tick_count, 1)
        self.assertEqual(batch.snapshot["device_id"], "ess-01")
        self.assertEqual(batch.telemetry_json, "telemetry:ess-01:30.0")
        self.assertEqual(batch.heartbeat_json, "heartbeat:PLANT-ALPHA:ess:ess-01")
        self.assertEqual(len(app.publisher.telemetry_inputs), 1)
        self.assertEqual(len(app.publisher.heartbeat_inputs), 1)
        self.assertEqual(
            app.publisher.heartbeat_inputs[0],
            ("PLANT-ALPHA", "ess", "ess-01"),
        )


if __name__ == "__main__":
    unittest.main()
