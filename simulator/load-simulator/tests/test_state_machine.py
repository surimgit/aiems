from __future__ import annotations

import unittest

from core.state_machine import (
    LoadOperatingState,
    is_transition_allowed,
    resolve_initial_state,
    resolve_runtime_state,
    validate_transition,
)


class LoadStateMachineUnitTest(unittest.TestCase):
    def test_enabled_device_starts_in_idle(self) -> None:
        self.assertEqual(resolve_initial_state(True), LoadOperatingState.IDLE)

    def test_disabled_device_starts_in_disabled(self) -> None:
        self.assertEqual(resolve_initial_state(False), LoadOperatingState.DISABLED)

    def test_running_to_shed_transition_is_allowed(self) -> None:
        self.assertTrue(
            is_transition_allowed(
                LoadOperatingState.RUNNING,
                LoadOperatingState.SHED,
            )
        )

    def test_invalid_transition_raises_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid transition"):
            validate_transition(
                LoadOperatingState.IDLE,
                LoadOperatingState.SHED,
            )

    def test_runtime_state_resolves_fault_before_shed(self) -> None:
        self.assertEqual(
            resolve_runtime_state(
                enabled=True,
                has_fault=True,
                shed_ratio=0.5,
                has_measurement=True,
            ),
            LoadOperatingState.FAULT,
        )

    def test_runtime_state_resolves_shed_when_ratio_is_present(self) -> None:
        self.assertEqual(
            resolve_runtime_state(
                enabled=True,
                has_fault=False,
                shed_ratio=0.2,
                has_measurement=True,
            ),
            LoadOperatingState.SHED,
        )


if __name__ == "__main__":
    unittest.main()
