from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from core.command_handler import LoadCommandHandler
from core.load import load_fleet_from_config
from core.scenario import LoadScenarioEngine, load_scenario_profiles
from core.state_machine import LoadOperatingState


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

    def test_preview_rejects_disabled_device(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)
        handler = LoadCommandHandler(fleet)

        resolution = handler.preview(
            device_id="load-03",
            payload={"command_type": "load_shed", "payload": {"reduction_ratio": 0.1}},
        )

        self.assertFalse(resolution.accepted)
        self.assertEqual(resolution.reason, "DEVICE_DISABLED")

    def test_handle_command_applies_shed_ratio_to_target_device(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)
        handler = LoadCommandHandler(fleet)
        device = fleet.get("load-01")

        ack = handler.handle_command(
            device_id="load-01",
            payload={
                "command_id": "cmd-101",
                "command_type": "load_shed",
                "payload": {"reduction_ratio": 0.25},
            },
        )

        self.assertEqual(ack.status, "accepted")
        self.assertEqual(device.state.shed_ratio, 0.25)
        self.assertEqual(device.state.last_command_id, "cmd-101")
        self.assertEqual(device.state.operating_state, LoadOperatingState.SHED)

    def test_handle_command_rejects_disabled_device(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)
        handler = LoadCommandHandler(fleet)
        device = fleet.get("load-03")

        ack = handler.handle_command(
            device_id="load-03",
            payload={
                "command_id": "cmd-102",
                "command_type": "load_shed",
                "payload": {"reduction_ratio": 0.25},
            },
        )

        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "DEVICE_DISABLED")
        self.assertEqual(device.state.shed_ratio, 0.0)

    def test_load_shed_changes_following_scenario_output(self) -> None:
        fleet = load_fleet_from_config(DEVICES_PATH)
        handler = LoadCommandHandler(fleet)
        engine = LoadScenarioEngine(load_scenario_profiles(BASE_DIR / "config" / "scenario.yaml"))
        device = fleet.get("load-02")
        observed_at = datetime(2026, 4, 22, 13, 0, tzinfo=timezone.utc)

        baseline_power = engine.calculate_active_power(device, observed_at)
        ack = handler.handle_command(
            device_id="load-02",
            payload={
                "command_id": "cmd-103",
                "command_type": "load_shed",
                "payload": {"reduction_ratio": 0.30},
            },
        )
        reduced_power = engine.calculate_active_power(device, observed_at)

        self.assertEqual(ack.status, "accepted")
        self.assertLess(reduced_power, baseline_power)


if __name__ == "__main__":
    unittest.main()
