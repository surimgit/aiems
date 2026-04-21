from __future__ import annotations

from datetime import datetime, timezone
import unittest

from mqtt_contract import (
    SimulatorSnapshot,
    build_heartbeat_message,
    build_heartbeat_topic,
    build_topic,
    parse_ess_command,
    parse_heartbeat_topic,
    parse_topic,
    snapshot_to_telemetry,
    to_simulator_command,
)


class MqttContractUnitTest(unittest.TestCase):
    def test_build_and_parse_topic(self) -> None:
        """일반 4세그먼트 토픽은 생성 후 다시 파싱해도 같은 값이 나와야 한다."""

        topic = build_topic("PLANT-ALPHA", "ess", "ess-01", "telemetry")

        parsed = parse_topic(topic)

        self.assertEqual(parsed.plant_id, "PLANT-ALPHA")
        self.assertEqual(parsed.resource_type, "ess")
        self.assertEqual(parsed.device_id, "ess-01")
        self.assertEqual(parsed.message_type, "telemetry")

    def test_build_and_parse_heartbeat_topic(self) -> None:
        """heartbeat 토픽은 문서에 맞는 2세그먼트 형태여야 한다."""

        topic = build_heartbeat_topic("PLANT-ALPHA")

        parsed = parse_heartbeat_topic(topic)

        self.assertEqual(topic, "PLANT-ALPHA/heartbeat")
        self.assertEqual(parsed.plant_id, "PLANT-ALPHA")
        self.assertEqual(parsed.message_type, "heartbeat")

    def test_build_heartbeat_message_uses_minimum_contract_shape(self) -> None:
        """heartbeat payload는 최소 식별 정보와 UTC 시각만 포함해야 한다."""

        message = build_heartbeat_message(
            "PLANT-ALPHA",
            "ess",
            "ess-01",
            timestamp=datetime(2026, 4, 14, 7, 50, tzinfo=timezone.utc),
        )

        self.assertEqual(message.plant_id, "PLANT-ALPHA")
        self.assertEqual(message.resource_type, "ess")
        self.assertEqual(message.device_id, "ess-01")
        self.assertEqual(message.timestamp, "2026-04-14T07:50:00Z")
        self.assertEqual(message.status, "alive")

    def test_parse_ess_command_and_convert_to_simulator_command(self) -> None:
        """MQTT 명령 모델이 내부 command 모델로 정상 변환돼야 한다."""

        payload = """
        {
          "command_id": "cmd-042",
          "command_type": "ess_mode",
          "payload": {
            "mode": "charge",
            "target_power_kw": 30.0
          }
        }
        """

        _, message = parse_ess_command("PLANT-ALPHA/ess/ess-01/command", payload, "PLANT-ALPHA", "ess-01")
        command = to_simulator_command(message)

        self.assertEqual(command.command_id, "cmd-042")
        self.assertEqual(command.command_type, "ess_mode")
        self.assertEqual(command.payload.mode, "charge")
        self.assertEqual(command.payload.target_power_kw, 30.0)

    def test_parse_ess_command_accepts_optional_control_metadata(self) -> None:
        """203 안전 제약에 필요한 추가 command metadata는 허용되어야 한다."""

        payload = """
        {
          "command_id": "cmd-044",
          "command_type": "ess_mode",
          "issued_at": "2026-04-14T07:49:00Z",
          "expires_in_sec": 30.0,
          "force": false,
          "source": "control-service",
          "payload": {
            "mode": "charge",
            "target_power_kw": 20.0
          }
        }
        """

        _, message = parse_ess_command("PLANT-ALPHA/ess/ess-01/command", payload, "PLANT-ALPHA", "ess-01")
        command = to_simulator_command(message)

        self.assertEqual(command.command_id, "cmd-044")
        self.assertEqual(command.expires_in_sec, 30.0)
        self.assertEqual(command.source, "control-service")

    def test_parse_ess_command_rejects_extra_fields_outside_contract(self) -> None:
        """문서에 없는 필드는 브로커 계약 위반으로 거부해야 한다."""

        payload = """
        {
          "command_id": "cmd-043",
          "command_type": "ess_mode",
          "payload": {
            "mode": "charge",
            "target_power_kw": 30.0,
            "unexpected": true
          }
        }
        """

        with self.assertRaises(ValueError):
            parse_ess_command("PLANT-ALPHA/ess/ess-01/command", payload, "PLANT-ALPHA", "ess-01")

    def test_snapshot_to_telemetry_uses_contract_shape(self) -> None:
        """snapshot을 telemetry로 바꿀 때 필수 필드가 빠지지 않아야 한다."""

        snapshot: SimulatorSnapshot = {
            "plant_id": "PLANT-ALPHA",
            "device_id": "ess-01",
            "resource_type": "ess",
            "soc": 67.3,
            "power_kw": 30.0,
            "operating_mode": "discharge",
            "accumulated_energy_kwh": 820.0,
        }

        message = snapshot_to_telemetry(
            snapshot,
            timestamp=datetime(2026, 4, 14, 7, 50, tzinfo=timezone.utc),
        )

        self.assertEqual(message.timestamp, "2026-04-14T07:50:00Z")
        self.assertEqual(message.data.instantaneous.P, 30.0)
        self.assertEqual(message.data.status.SOC, 67.3)
        self.assertEqual(message.data.status.operating_mode, "discharge")

    def test_snapshot_to_telemetry_keeps_charge_sign_and_absolute_current(self) -> None:
        """충전 telemetry는 P 음수, 전류는 절대값 기준으로 직렬화해야 한다."""

        snapshot: SimulatorSnapshot = {
            "plant_id": "PLANT-ALPHA",
            "device_id": "ess-01",
            "resource_type": "ess",
            "soc": 72.5,
            "power_kw": -38.0,
            "operating_mode": "charge",
            "accumulated_energy_kwh": 900.0,
        }

        message = snapshot_to_telemetry(
            snapshot,
            timestamp=datetime(2026, 4, 14, 7, 50, tzinfo=timezone.utc),
        )

        self.assertEqual(message.data.instantaneous.P, -38.0)
        self.assertAlmostEqual(message.data.instantaneous.I, 0.1, places=3)
        self.assertEqual(message.data.status.operating_mode, "charge")

    def test_parse_ess_command_rejects_command_for_other_device(self) -> None:
        """다른 device 대상 명령은 현재 simulator에서 바로 거부해야 한다."""

        payload = """
        {
          "command_id": "cmd-045",
          "command_type": "ess_mode",
          "payload": {
            "mode": "charge",
            "target_power_kw": 20.0
          }
        }
        """

        with self.assertRaises(ValueError):
            parse_ess_command("PLANT-ALPHA/ess/ess-02/command", payload, "PLANT-ALPHA", "ess-01")


if __name__ == "__main__":
    unittest.main()
