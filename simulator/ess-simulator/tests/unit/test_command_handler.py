from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest

from core.command_handler import CommandHandler, parse_simulator_command
from core.ess import DeviceSpec, EssSimulator, SafetySpec


def build_handler(*, initial_soc: float = 50.0, temperature_c: float = 25.0) -> CommandHandler:
    """명령 처리 테스트용 ESS handler를 공통 설정으로 만든다."""

    simulator = EssSimulator(
        device_spec=DeviceSpec(
            plant_id="PLANT-ALPHA",
            device_id="ess-01",
            resource_type="ess",
            publish_interval_sec=1.0,
            power_limit_kw=40.0,
            capacity_kwh=500.0,
        ),
        safety_spec=SafetySpec(
            low_soc_threshold=20.0,
            high_soc_threshold=80.0,
            min_safe_soc_threshold=5.0,
            max_safe_soc_threshold=95.0,
            max_temperature_c=45.0,
        ),
        initial_soc=initial_soc,
        temperature_c=temperature_c,
    )
    return CommandHandler(simulator)


class CommandHandlerUnitTest(unittest.TestCase):
    def test_handle_command_accepts_ess_mode_and_returns_applied_payload(self) -> None:
        """정상 ess_mode 명령은 적용값이 담긴 accepted ACK를 반환해야 한다."""

        handler = build_handler()
        command = parse_simulator_command(
            {
                "command_id": "cmd-201",
                "command_type": "ess_mode",
                "payload": {"mode": "charge", "target_power_kw": 12.5},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "accepted")
        self.assertEqual(ack.applied, {"mode": "charge", "target_power_kw": 12.5})

    def test_handle_command_rejects_when_device_is_busy(self) -> None:
        """IN_PROGRESS 상태에서는 DEVICE_BUSY reason code로 거부해야 한다."""

        handler = build_handler()
        handler.simulator.status.state = "IN_PROGRESS"
        command = parse_simulator_command(
            {
                "command_id": "cmd-202",
                "command_type": "ess_mode",
                "payload": {"mode": "discharge", "target_power_kw": 15.0},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "DEVICE_BUSY")

    def test_handle_command_rejects_when_charge_is_safety_blocked(self) -> None:
        """안전 임계값 위반 충전 명령은 LOCAL_SAFETY_BLOCKED로 거부해야 한다."""

        handler = build_handler(initial_soc=85.0)
        command = parse_simulator_command(
            {
                "command_id": "cmd-203",
                "command_type": "ess_mode",
                "payload": {"mode": "charge", "target_power_kw": 10.0},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "LOCAL_SAFETY_BLOCKED")

    def test_handle_command_applies_device_spec_updates(self) -> None:
        """스펙 변경 명령은 반영된 필드만 applied에 담아 반환해야 한다."""

        handler = build_handler()
        command = parse_simulator_command(
            {
                "command_id": "cmd-204",
                "command_type": "update_device_spec",
                "payload": {"power_limit_kw": 30.0, "publish_interval_sec": 2.0},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "accepted")
        self.assertEqual(ack.applied, {"power_limit_kw": 30.0, "publish_interval_sec": 2.0})

    def test_handle_command_rejects_when_interlock_is_active(self) -> None:
        """인터락 상태에서는 INTERLOCK_VIOLATION으로 거부해야 한다."""

        handler = build_handler()
        handler.simulator.set_interlock_active(True)
        command = parse_simulator_command(
            {
                "command_id": "cmd-205",
                "command_type": "ess_mode",
                "payload": {"mode": "charge", "target_power_kw": 10.0},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "INTERLOCK_VIOLATION")

    def test_handle_command_rejects_when_comms_is_unhealthy(self) -> None:
        """통신 장애 상태에서는 NO_DEVICE_ACK로 거부해야 한다."""

        handler = build_handler()
        handler.simulator.set_comms_health(False)
        command = parse_simulator_command(
            {
                "command_id": "cmd-206",
                "command_type": "ess_mode",
                "payload": {"mode": "discharge", "target_power_kw": 10.0},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "NO_DEVICE_ACK")

    def test_handle_command_rejects_when_command_is_expired(self) -> None:
        """유효 시간이 지난 명령은 COMMAND_EXPIRED로 거부해야 한다."""

        handler = build_handler()
        command = parse_simulator_command(
            {
                "command_id": "cmd-207",
                "command_type": "ess_mode",
                "issued_at": (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat(),
                "expires_in_sec": 5.0,
                "payload": {"mode": "charge", "target_power_kw": 10.0},
            }
        )

        ack = handler.handle_command(command)

        self.assertEqual(ack.status, "rejected")
        self.assertEqual(ack.reason, "COMMAND_EXPIRED")


if __name__ == "__main__":
    unittest.main()
