from __future__ import annotations

import unittest

from core.state_machine import (
    is_transition_allowed,
    resolve_safety_state,
    resolve_state_for_mode,
    sync_state_with_mode,
    validate_mode_transition,
)


class StateMachineUnitTest(unittest.TestCase):
    def test_validate_mode_transition_returns_target_state(self) -> None:
        """대기 상태에서 충전 명령은 CHARGING 목표 상태로 해석되어야 한다."""
        next_state = validate_mode_transition(
            current_state="STANDBY",
            current_mode="standby",
            requested_mode="charge",
            local_fault=False,
            emergency_stop=False,
        )

        self.assertEqual(next_state, "CHARGING")

    def test_validate_mode_transition_rejects_duplicate_state(self) -> None:
        """같은 상태로의 중복 명령은 거절되어야 한다."""
        with self.assertRaisesRegex(ValueError, "ALREADY_IN_STATE"):
            validate_mode_transition(
                current_state="CHARGING",
                current_mode="charge",
                requested_mode="charge",
                local_fault=False,
                emergency_stop=False,
            )

    def test_validate_mode_transition_rejects_busy_state(self) -> None:
        """IN_PROGRESS 상태에서는 새 명령을 받지 않아야 한다."""
        with self.assertRaisesRegex(ValueError, "DEVICE_BUSY"):
            validate_mode_transition(
                current_state="IN_PROGRESS",
                current_mode="standby",
                requested_mode="discharge",
                local_fault=False,
                emergency_stop=False,
            )

    def test_transition_table_allows_safe_stop_from_any_state(self) -> None:
        """안전 정지는 어떤 상태에서도 가능해야 한다."""
        self.assertTrue(is_transition_allowed("CHARGING", "SAFE_STOP"))
        self.assertTrue(is_transition_allowed("DISCHARGING", "SAFE_STOP"))

    def test_resolve_safety_state_distinguishes_fault_and_safe_stop(self) -> None:
        """로컬 fault 여부에 따라 FAULT와 SAFE_STOP을 구분해야 한다."""
        self.assertEqual(resolve_safety_state(True, True), "FAULT")
        self.assertEqual(resolve_safety_state(True, False), "SAFE_STOP")

    def test_sync_state_with_mode_uses_operating_mode_when_normal(self) -> None:
        """정상 상태에서는 운전 모드에 맞춰 표시 상태가 동기화되어야 한다."""
        state = sync_state_with_mode(
            current_state="IN_PROGRESS",
            operating_mode="discharge",
            local_fault=False,
            emergency_stop=False,
        )

        self.assertEqual(state, resolve_state_for_mode("discharge"))


if __name__ == "__main__":
    unittest.main()
