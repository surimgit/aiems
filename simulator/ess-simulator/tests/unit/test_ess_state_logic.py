from __future__ import annotations

import unittest

from core.ess import DeviceSpec, EssSimulator, SafetySpec


class EssStateLogicUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        """상태 전이와 안전 규칙을 검증할 기본 시뮬레이터를 만든다."""
        self.simulator = EssSimulator(
            device_spec=DeviceSpec(
                plant_id="PLANT-ALPHA",
                device_id="ess-01",
                resource_type="ess",
                publish_interval_sec=0.1,
                power_limit_kw=40.0,
                capacity_kwh=500.0,
            ),
            safety_spec=SafetySpec(
                low_soc_threshold=20.0,
                high_soc_threshold=80.0,
                min_safe_soc_threshold=10.0,
                max_safe_soc_threshold=95.0,
                max_temperature_c=45.0,
            ),
            initial_soc=50.0,
        )

    def test_set_mode_moves_to_charging_state(self) -> None:
        """충전 명령이 수락되면 상태와 전력 부호가 함께 반영되어야 한다."""
        self.simulator.set_mode("charge", 15.0)
        snapshot = self.simulator.snapshot()

        self.assertEqual(snapshot["state"], "CHARGING")
        self.assertEqual(snapshot["operating_mode"], "charge")
        self.assertEqual(snapshot["power_kw"], -15.0)

    def test_tick_enters_safe_stop_when_soc_reaches_minimum_safe_threshold(self) -> None:
        """방전 중 최소 안전 SOC를 넘기면 SAFE_STOP으로 떨어져야 한다."""
        self.simulator.status.soc = 10.01
        self.simulator.device_spec.capacity_kwh = 1.0
        self.simulator.status.state = "DISCHARGING"
        self.simulator.status.operating_mode = "discharge"
        self.simulator.status.target_power_kw = 40.0
        self.simulator.status.power_kw = 40.0

        snapshot = self.simulator.tick()

        self.assertEqual(snapshot["state"], "SAFE_STOP")
        self.assertEqual(snapshot["operating_mode"], "standby")
        self.assertEqual(snapshot["power_kw"], 0.0)

    def test_tick_enters_fault_when_temperature_exceeds_limit(self) -> None:
        """과온은 일반 safe stop이 아니라 fault로 분류되어야 한다."""
        self.simulator.set_mode("charge", 10.0)
        self.simulator.status.temperature_c = 50.0

        snapshot = self.simulator.tick()

        self.assertEqual(snapshot["state"], "FAULT")
        self.assertTrue(snapshot["local_fault"])
        self.assertEqual(snapshot["operating_mode"], "standby")

    def test_tick_updates_soc_from_capacity_based_energy_model(self) -> None:
        """SOC는 power limit이 아니라 capacity_kwh 기준으로 변해야 한다."""
        self.simulator.set_mode("charge", 40.0)

        snapshot = self.simulator.tick()

        self.assertAlmostEqual(self.simulator.status.soc, 50.0002222222, places=6)
        self.assertAlmostEqual(self.simulator.status.accumulated_energy_kwh, 0.0011111111, places=6)
        self.assertEqual(snapshot["publish_interval_sec"], 0.1)

    def test_update_device_spec_changes_capacity_kwh(self) -> None:
        """장치 스펙 변경 명령으로 배터리 용량을 바꿀 수 있어야 한다."""
        applied = self.simulator.update_device_spec(capacity_kwh=250.0)
        snapshot = self.simulator.snapshot()

        self.assertEqual(applied, {"capacity_kwh": 250.0})
        self.assertEqual(snapshot["capacity_kwh"], 250.0)


if __name__ == "__main__":
    unittest.main()
