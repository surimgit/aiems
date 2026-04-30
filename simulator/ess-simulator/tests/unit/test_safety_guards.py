from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from core.safety_guards import (
    ensure_command_not_expired,
    ensure_comms_healthy,
    ensure_emergency_not_active,
    ensure_interlock_clear,
    ensure_local_safety_clear,
)


class SafetyGuardsUnitTest(unittest.TestCase):
    def test_expired_command_is_blocked(self) -> None:
        """유효 시간을 넘긴 명령은 COMMAND_EXPIRED로 차단해야 한다."""

        issued_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        with self.assertRaisesRegex(ValueError, "COMMAND_EXPIRED"):
            ensure_command_not_expired(
                issued_at=issued_at,
                expires_in_sec=5.0,
                current_time=datetime.now(timezone.utc),
            )

    def test_interlock_is_blocked(self) -> None:
        """인터락이 걸려 있으면 INTERLOCK_VIOLATION이어야 한다."""

        with self.assertRaisesRegex(ValueError, "INTERLOCK_VIOLATION"):
            ensure_interlock_clear(interlock_active=True)

    def test_comms_failure_is_blocked(self) -> None:
        """통신 장애는 NO_DEVICE_ACK로 차단해야 한다."""

        with self.assertRaisesRegex(ValueError, "NO_DEVICE_ACK"):
            ensure_comms_healthy(comms_healthy=False)

    def test_emergency_state_is_blocked(self) -> None:
        """비상 정지 상태는 EMERGENCY_STOP_ACTIVE로 차단해야 한다."""

        with self.assertRaisesRegex(ValueError, "EMERGENCY_STOP_ACTIVE"):
            ensure_emergency_not_active(emergency_stop=True, current_state="STANDBY")

    def test_local_fault_is_blocked(self) -> None:
        """로컬 fault는 LOCAL_SAFETY_BLOCKED로 차단해야 한다."""

        with self.assertRaisesRegex(ValueError, "LOCAL_SAFETY_BLOCKED"):
            ensure_local_safety_clear(local_fault=True)


if __name__ == "__main__":
    unittest.main()
