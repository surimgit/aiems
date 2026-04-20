from __future__ import annotations

import json
import unittest

from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandAck
from mqtt_contract import SimulatorSnapshot


class ClientSpy:
    """퍼블리셔가 실제 MQTT 클라이언트 대신 호출하는 테스트 더블이다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def publish(self, topic: str, payload: str, qos: int = 0) -> None:
        self.calls.append((topic, payload, qos))

    def connect(self, host: str, port: int, keepalive: int = 60) -> None:
        return None

    def loop_start(self) -> None:
        return None

    def loop_stop(self) -> None:
        return None

    def disconnect(self) -> None:
        return None


class MqttPublisherIntegrationTest(unittest.TestCase):
    def test_publish_telemetry_uses_contract_topic_and_payload(self) -> None:
        """telemetry 발행 시 토픽과 payload 형식이 계약과 일치해야 한다."""

        publisher = MqttPublisher("localhost", 1883)
        client = ClientSpy()
        publisher.client = client
        publisher.connected = True

        snapshot: SimulatorSnapshot = {
            "plant_id": "PLANT-ALPHA",
            "device_id": "ess-01",
            "resource_type": "ess",
            "soc": 50.0,
            "power_kw": 20.0,
            "operating_mode": "discharge",
            "accumulated_energy_kwh": 10.0,
        }

        publisher.publish_telemetry(snapshot)

        self.assertEqual(len(client.calls), 1)
        topic, payload, qos = client.calls[0]
        body = json.loads(payload)
        self.assertEqual(topic, "PLANT-ALPHA/ess/ess-01/telemetry")
        self.assertEqual(qos, 1)
        self.assertEqual(body["resource_type"], "ess")
        self.assertEqual(body["data"]["status"]["operating_mode"], "discharge")

    def test_publish_ack_uses_ack_contract(self) -> None:
        """ACK 발행 시 topic, QoS, JSON 형식이 올바라야 한다."""

        publisher = MqttPublisher("localhost", 1883)
        client = ClientSpy()
        publisher.client = client
        publisher.connected = True

        publisher.publish_ack(
            "PLANT-ALPHA",
            "ess",
            "ess-01",
            CommandAck(command_id="cmd-003", status="accepted"),
        )

        self.assertEqual(len(client.calls), 1)
        topic, payload, qos = client.calls[0]
        body = json.loads(payload)
        self.assertEqual(topic, "PLANT-ALPHA/ess/ess-01/ack")
        self.assertEqual(qos, 1)
        self.assertEqual(body, {"command_id": "cmd-003", "status": "accepted"})

    def test_publish_heartbeat_uses_heartbeat_topic_and_payload(self) -> None:
        """heartbeat는 2세그먼트 토픽과 최소 생존 신호 payload를 사용해야 한다."""

        publisher = MqttPublisher("localhost", 1883)
        client = ClientSpy()
        publisher.client = client
        publisher.connected = True

        publisher.publish_heartbeat("PLANT-ALPHA", "ess", "ess-01")

        self.assertEqual(len(client.calls), 1)
        topic, payload, qos = client.calls[0]
        body = json.loads(payload)
        self.assertEqual(topic, "PLANT-ALPHA/heartbeat")
        self.assertEqual(qos, 1)
        self.assertEqual(body["plant_id"], "PLANT-ALPHA")
        self.assertEqual(body["resource_type"], "ess")
        self.assertEqual(body["device_id"], "ess-01")
        self.assertEqual(body["status"], "alive")


if __name__ == "__main__":
    unittest.main()
