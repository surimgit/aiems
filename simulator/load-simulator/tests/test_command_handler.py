from __future__ import annotations

import unittest
from pathlib import Path

from core.command_handler import LoadCommandHandler
from core.load import load_fleet_from_config


BASE_DIR = Path(__file__).resolve().parents[1]
DEVICES_PATH = BASE_DIR / "config" / "devices.yaml"


class LoadCommandHandlerUnitTest(unittest.TestCase):
    def test_preview_accepts_known_device(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)
        handler = LoadCommandHandler(fleet)

        resolution = handler.preview(
            device_id="load-01",
            payload={"command_type": "load_shed", "payload": {"reduction_ratio": 0.1}},
        )

        self.assertTrue(resolution.accepted)
        self.assertEqual(resolution.device_id, "load-01")

    def test_preview_rejects_unknown_device(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)
        handler = LoadCommandHandler(fleet)

        resolution = handler.preview(
            device_id="load-99",
            payload={"command_type": "load_shed", "payload": {"reduction_ratio": 0.1}},
        )

        self.assertFalse(resolution.accepted)
        self.assertEqual(resolution.reason, "DEVICE_NOT_FOUND: load-99")


if __name__ == "__main__":
    unittest.main()
