from __future__ import annotations

from typing import Any, Protocol

import paho.mqtt.client as mqtt

from core.command_handler import CommandAck
from mqtt_contract import SimulatorSnapshot, build_topic, snapshot_to_telemetry, to_ack_message


class PublisherClient(Protocol):
    """Publisher가 실제 MQTT 클라이언트에 기대하는 최소 기능이다."""

    def publish(self, topic: str, payload: str, qos: int = 0) -> Any:
        ...

    def connect(self, host: str, port: int, keepalive: int = 60) -> Any:
        ...

    def loop_start(self) -> Any:
        ...

    def loop_stop(self) -> Any:
        ...

    def disconnect(self) -> Any:
        ...


class MqttPublisher:
    def __init__(self, broker_host: str, broker_port: int) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client: PublisherClient = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    @staticmethod
    def build_topic(plant_id: str, resource_type: str, device_id: str, message_type: str) -> str:
        """공통 계약 함수를 써서 토픽을 만든다."""

        return build_topic(plant_id, resource_type, device_id, message_type)

    def start(self) -> None:
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            print(f"[ESS][mqtt] publisher connection skipped: {exc}")

    def stop(self) -> None:
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()

    @staticmethod
    def serialize_telemetry(snapshot: SimulatorSnapshot) -> str:
        """정형 snapshot을 telemetry JSON 문자열로 직렬화한다."""

        return snapshot_to_telemetry(snapshot).model_dump_json()

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        """내부 ACK 객체를 외부 전송용 JSON으로 직렬화한다."""

        return to_ack_message(ack).model_dump_json(exclude_none=True)

    def publish_telemetry(self, snapshot: SimulatorSnapshot) -> None:
        """연결된 상태에서만 telemetry를 발행한다."""

        if not self.connected:
            return
        topic = self.build_topic(snapshot["plant_id"], snapshot["resource_type"], snapshot["device_id"], "telemetry")
        self.client.publish(topic, self.serialize_telemetry(snapshot), qos=1)

    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        """연결된 상태에서만 ACK를 발행한다."""

        if not self.connected:
            return
        topic = self.build_topic(plant_id, resource_type, device_id, "ack")
        self.client.publish(topic, self.serialize_ack(ack), qos=1)

    def _on_connect(self, _client: mqtt.Client, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = True
        print(f"[ESS][mqtt] publisher connected to {self.broker_host}:{self.broker_port}")

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, _disconnect_flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = False
