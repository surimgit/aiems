from __future__ import annotations

import json
from typing import Any, Protocol

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError:  # pragma: no cover
    mqtt = None

from adapters.outbound.heartbeat_publisher import resolve_heartbeat_topic, serialize_heartbeat
from core.command_handler import CommandAck
from core.load import LoadDevice
from mqtt_contract import RESOURCE_TYPE, ack_to_payload, build_topic, snapshot_to_telemetry


class PublisherClient(Protocol):
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
    # 브로커 접속 정보와 MQTT 클라이언트를 초기화한다.
    def __init__(self, broker_host: str, broker_port: int) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.connected = False
        if mqtt is None:
            self.client = None
            return
        self.client: PublisherClient = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    # MQTT 계약 규칙에 맞는 토픽 문자열을 만든다.
    @staticmethod
    def build_topic(site_id: str, resource_type: str, device_id: str, message_type: str) -> str:
        return build_topic(site_id, resource_type, device_id, message_type)

    # 장치 스냅샷을 telemetry JSON으로 직렬화한다.
    @staticmethod
    def serialize_telemetry(device: LoadDevice, *, wire_fault: bool = False) -> str:
        return json.dumps(snapshot_to_telemetry(device, wire_fault=wire_fault), separators=(",", ":"))

    # ACK 객체를 MQTT 응답 JSON으로 직렬화한다.
    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        return json.dumps(ack_to_payload(ack), separators=(",", ":"))

    # heartbeat 메시지를 JSON 문자열로 직렬화한다.
    @staticmethod
    def serialize_heartbeat(site_id: str, device_id: str) -> str:
        return serialize_heartbeat(site_id, device_id)

    # MQTT 브로커 연결과 백그라운드 루프를 시작한다.
    def start(self) -> None:
        if self.client is None:
            return
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            print(f"[LOAD][mqtt] publisher connection skipped: {exc}")

    # 실행 중인 MQTT 루프를 정리하고 연결을 닫는다.
    def stop(self) -> None:
        if self.client is None or not self.connected:
            return
        self.client.loop_stop()
        self.client.disconnect()

    # 분전함 telemetry를 MQTT로 발행한다.
    def publish_telemetry(self, device: LoadDevice, *, wire_fault: bool = False) -> None:
        if self.client is None or not self.connected:
            return
        topic = self.build_topic(device.site_id, RESOURCE_TYPE, device.device_id, "telemetry")
        self.client.publish(topic, self.serialize_telemetry(device, wire_fault=wire_fault), qos=1)

    # 명령 처리 결과 ACK를 MQTT로 발행한다.
    def publish_ack(self, site_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        if self.client is None or not self.connected:
            return
        topic = self.build_topic(site_id, resource_type, device_id, "ack")
        self.client.publish(topic, self.serialize_ack(ack), qos=1)

    # 사이트 생존 신호용 heartbeat를 MQTT로 발행한다.
    def publish_heartbeat(self, site_id: str, resource_type: str, device_id: str) -> None:
        if self.client is None or not self.connected:
            return
        topic = resolve_heartbeat_topic(site_id)
        self.client.publish(topic, self.serialize_heartbeat(site_id, device_id), qos=1)

    # 브로커 연결 성공 시 내부 연결 상태를 갱신한다.
    def _on_connect(self, _client: Any, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = True

    # 브로커 연결 종료 시 내부 연결 상태를 해제한다.
    def _on_disconnect(self, _client: Any, _userdata: Any, _disconnect_flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = False
