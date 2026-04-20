from __future__ import annotations

from typing import Any, Protocol

import paho.mqtt.client as mqtt

from adapters.outbound.heartbeat_publisher import resolve_heartbeat_topic, serialize_heartbeat
from core.command_handler import CommandAck
from mqtt_contract import SimulatorSnapshot, build_topic, snapshot_to_telemetry, to_ack_message


class PublisherClient(Protocol):
    """실제 MQTT 클라이언트가 제공해야 하는 최소 기능 집합이다."""

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
    """ESS 시뮬레이터가 브로커로 보내는 MQTT 메시지 출구를 담당한다."""

    def __init__(self, broker_host: str, broker_port: int) -> None:
        """브로커 접속 정보와 MQTT 콜백을 초기화한다."""

        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client: PublisherClient = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    @staticmethod
    def build_topic(plant_id: str, resource_type: str, device_id: str, message_type: str) -> str:
        """일반 MQTT 계약의 4세그먼트 토픽을 생성한다."""

        return build_topic(plant_id, resource_type, device_id, message_type)

    def start(self) -> None:
        """브로커 연결을 시도하고 백그라운드 네트워크 루프를 시작한다."""

        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            print(f"[ESS][mqtt] publisher connection skipped: {exc}")

    def stop(self) -> None:
        """연결된 경우에만 MQTT 네트워크 루프와 연결을 정리한다."""

        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()

    @staticmethod
    def serialize_telemetry(snapshot: SimulatorSnapshot) -> str:
        """시뮬레이터 snapshot을 브로커 telemetry JSON으로 직렬화한다."""

        return snapshot_to_telemetry(snapshot).model_dump_json()

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        """내부 ACK 모델을 MQTT ACK JSON으로 직렬화한다."""

        return to_ack_message(ack).model_dump_json(exclude_none=True)

    @staticmethod
    def serialize_heartbeat(plant_id: str, resource_type: str, device_id: str) -> str:
        """heartbeat 최소 생존 신호 payload를 JSON으로 직렬화한다."""

        return serialize_heartbeat(plant_id, resource_type, device_id)

    def publish_telemetry(self, snapshot: SimulatorSnapshot) -> None:
        """연결된 경우에만 telemetry를 문서 규격 토픽으로 발행한다."""

        if not self.connected:
            return
        topic = self.build_topic(snapshot["plant_id"], snapshot["resource_type"], snapshot["device_id"], "telemetry")
        self.client.publish(topic, self.serialize_telemetry(snapshot), qos=1)

    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        """연결된 경우에만 ACK를 문서 규격 토픽으로 발행한다."""

        if not self.connected:
            return
        topic = self.build_topic(plant_id, resource_type, device_id, "ack")
        self.client.publish(topic, self.serialize_ack(ack), qos=1)

    def publish_heartbeat(self, plant_id: str, resource_type: str, device_id: str) -> None:
        """연결된 경우에만 heartbeat를 문서 규격 토픽으로 발행한다."""

        if not self.connected:
            return
        topic = resolve_heartbeat_topic(plant_id)
        self.client.publish(topic, self.serialize_heartbeat(plant_id, resource_type, device_id), qos=1)

    def _on_connect(self, _client: mqtt.Client, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        """브로커 연결 성공 시 내부 연결 상태를 갱신한다."""

        self.connected = True
        print(f"[ESS][mqtt] publisher connected to {self.broker_host}:{self.broker_port}")

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, _disconnect_flags: Any, _reason_code: Any, _properties: Any) -> None:
        """브로커 연결이 끊기면 내부 연결 상태를 해제한다."""

        self.connected = False
