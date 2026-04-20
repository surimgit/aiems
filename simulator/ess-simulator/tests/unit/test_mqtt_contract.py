from __future__ import annotations

from datetime import datetime, timezone
import unittest

from mqtt_contract import (
    SimulatorSnapshot,
    build_topic,
    parse_ess_command,
    parse_topic,
    snapshot_to_telemetry,
    to_simulator_command,
)


class MqttContractUnitTest(unittest.TestCase):
    def test_build_and_parse_topic(self) -> None:
        """토픽 생성 결과가 다시 파싱돼도 같은 값이 나와야 한다."""
        topic = build_topic("PLANT-ALPHA", "ess", "ess-01", "telemetry")

        parsed = parse_topic(topic)

        self.assertEqual(parsed.plant_id, "PLANT-ALPHA")
        self.assertEqual(parsed.resource_type, "ess")
        self.assertEqual(parsed.device_id, "ess-01")
        self.assertEqual(parsed.message_type, "telemetry")

    def test_parse_ess_command_and_convert_to_simulator_command(self) -> None:
        """MQTT command 모델이 내부 command 모델로 정상 변환돼야 한다."""
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


if __name__ == "__main__":
    unittest.main()
