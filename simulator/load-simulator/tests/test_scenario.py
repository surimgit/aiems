from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.load import load_fleet_from_config
from core.scenario import LoadScenarioEngine, load_scenario_profiles
from core.state_machine import LoadOperatingState


class LoadScenarioEngineUnitTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fleet = load_fleet_from_config("config/devices.yaml")
        self.profiles = load_scenario_profiles("config/scenario.yaml")
        self.engine = LoadScenarioEngine(self.profiles)

    def test_peak_hour_profile_produces_more_than_off_peak(self) -> None:
        device = self.fleet.get("load-01")

        peak_power = self.engine.calculate_active_power(
            device,
            datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
        )
        off_peak_power = self.engine.calculate_active_power(
            device,
            datetime(2026, 4, 22, 3, 0, tzinfo=timezone.utc),
        )

        self.assertGreater(peak_power, off_peak_power)

    def test_tick_device_updates_energy_and_runtime_state(self) -> None:
        device = self.fleet.get("load-01")

        measurement = self.engine.tick_device(
            device,
            datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc),
            elapsed_seconds=3600,
        )

        self.assertGreater(measurement.kwh, 0.0)
        self.assertEqual(device.state.operating_state, LoadOperatingState.RUNNING)

    def test_shed_ratio_reduces_generated_power(self) -> None:
        device = self.fleet.get("load-02")
        observed_at = datetime(2026, 4, 22, 13, 0, tzinfo=timezone.utc)

        unshed_power = self.engine.calculate_active_power(device, observed_at)
        device.set_shed_ratio(0.25)
        shed_power = self.engine.calculate_active_power(device, observed_at)

        self.assertLess(shed_power, unshed_power)
        self.assertEqual(device.state.operating_state, LoadOperatingState.SHED)

    def test_tick_fleet_updates_only_enabled_devices(self) -> None:
        results = self.engine.tick_fleet(
            self.fleet,
            datetime(2026, 4, 22, 9, 0, tzinfo=timezone.utc),
            elapsed_seconds=300,
        )

        self.assertEqual(set(results), {"load-01", "load-02"})
        self.assertNotIn("load-03", results)

    def test_profiles_expose_extended_configuration(self) -> None:
        profile = self.profiles["office-day"]

        self.assertEqual(profile.off_peak_multiplier, 0.85)
        self.assertEqual(profile.weekend_multiplier, 0.70)
        self.assertEqual(profile.minimum_load_ratio, 0.15)


if __name__ == "__main__":
    unittest.main()
