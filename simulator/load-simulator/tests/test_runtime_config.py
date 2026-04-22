from __future__ import annotations

import unittest
from pathlib import Path

from runtime_config import load_config


BASE_DIR = Path(__file__).resolve().parents[1]


class RuntimeConfigUnitTest(unittest.TestCase):
    def test_load_config_reads_runtime_and_device_settings(self) -> None:
        config = load_config(
            BASE_DIR / "config" / "devices.yaml",
            BASE_DIR / "config" / "scenario.yaml",
        )

        self.assertEqual(config.site_id, "PLANT-ALPHA")
        self.assertEqual(config.edge_id, "edge-01")
        self.assertEqual(config.mqtt_broker_host, "localhost")
        self.assertEqual(config.mqtt_broker_port, 1883)
        self.assertEqual(config.publish_interval_sec, 1.0)
        self.assertEqual(len(config.fleet.list_enabled()), 2)
        self.assertIn("office-day", config.scenario_profiles)


if __name__ == "__main__":
    unittest.main()
