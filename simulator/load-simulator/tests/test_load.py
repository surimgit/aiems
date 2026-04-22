from __future__ import annotations

import unittest
from pathlib import Path

from core.load import LoadDevice, LoadDeviceConfig, LoadFleet, LoadMeasurement, load_device_configs, load_fleet_from_config
from core.scenario import load_scenario_profiles


BASE_DIR = Path(__file__).resolve().parents[1]
DEVICES_PATH = BASE_DIR / "config" / "devices.yaml"
SCENARIO_PATH = BASE_DIR / "config" / "scenario.yaml"


class LoadDomainModelUnitTest(unittest.TestCase):
    def test_load_device_configs_support_multiple_panels(self) -> None:
        configs = load_device_configs(DEVICES_PATH)

        self.assertEqual(len(configs), 3)
        self.assertEqual(configs[0].device_id, "load-01")
        self.assertEqual(configs[1].panel_id, "panel-02")
        self.assertFalse(configs[2].enabled)

    def test_load_fleet_builds_enabled_and_disabled_devices(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)

        self.assertEqual(len(fleet.list_all()), 3)
        self.assertEqual(len(fleet.list_enabled()), 2)
        self.assertEqual(fleet.get("load-02").panel_id, "panel-02")
        self.assertEqual(fleet.get_by_panel_id("panel-03").device_id, "load-03")

    def test_total_power_uses_enabled_devices_only_by_default(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)

        self.assertEqual(fleet.total_base_power_kw(), 125.0)
        self.assertEqual(fleet.total_base_power_kw(enabled_only=False), 145.0)

    def test_measurement_factory_derives_electrical_values(self) -> None:
        measurement = LoadMeasurement.from_active_power(
            p_kw=50.0,
            voltage_v=380.0,
            frequency_hz=60.0,
            power_factor=0.95,
        )

        self.assertAlmostEqual(measurement.p_kw, 50.0)
        self.assertGreater(measurement.q_kvar, 0.0)
        self.assertGreater(measurement.i_a, 0.0)
        self.assertEqual(measurement.demand_max_kw, 50.0)

    def test_duplicate_device_ids_are_rejected(self) -> None:
        fleet = LoadFleet(site_id="PLANT-ALPHA", edge_id="edge-01")
        config = LoadDeviceConfig(
            site_id="PLANT-ALPHA",
            edge_id="edge-01",
            device_id="load-01",
            panel_id="panel-01",
            name="office-panel",
            rated_kw=10.0,
            base_kw=5.0,
            power_factor=0.9,
            voltage_v=380.0,
            frequency_hz=60.0,
            enabled=True,
            scenario_profile="office-day",
        )

        fleet.register(LoadDevice.from_config(config))

        with self.assertRaisesRegex(ValueError, "duplicate device_id"):
            fleet.register(
                LoadDevice.from_config(
                    LoadDeviceConfig(
                        site_id="PLANT-ALPHA",
                        edge_id="edge-01",
                        device_id="load-01",
                        panel_id="panel-02",
                        name="hvac-panel",
                        rated_kw=20.0,
                        base_kw=8.0,
                        power_factor=0.95,
                        voltage_v=380.0,
                        frequency_hz=60.0,
                        enabled=True,
                        scenario_profile="hvac-heavy",
                    )
                )
            )

    def test_scenario_profiles_are_loaded_for_later_tasks(self) -> None:
        profiles = load_scenario_profiles(SCENARIO_PATH)

        self.assertEqual(set(profiles), {"office-day", "hvac-heavy", "off-hours"})
        self.assertEqual(profiles["hvac-heavy"].peak_multiplier, 1.35)


if __name__ == "__main__":
    unittest.main()
