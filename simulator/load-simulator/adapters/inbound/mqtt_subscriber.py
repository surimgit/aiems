from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Protocol

try:
    import paho.mqtt.client as mqtt
except ModuleNotFoundError:  # pragma: no cover
    mqtt = None

from core.command_handler import CommandAck, LoadCommandHandler
from mqtt_contract import RESOURCE_TYPE, parse_load_command


class AckPublisher(Protocol):
    def publish_ack(self, site_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        ...

    def serialize_ack(self, ack: CommandAck) -> str:
        ...


class InboundMqttMessage(Protocol):
    topic: str
    payload: bytes | str


class MqttCommandSubscriber:
    # 구독 대상과 ACK 발행기를 묶어 MQTT subscriber를 초기화한다.
    def __init__(
        self,
        handler: LoadCommandHandler,
        publisher: AckPublisher,
        site_id: str,
        resource_type: str,
        broker_host: str,
        broker_port: int,
    ) -> None:
        self.handler = handler
        self.publisher = publisher
        self.site_id = site_id
        self.resource_type = resource_type
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.connected = False
        if mqtt is None:
            self.client = None
            return
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    # 수신된 MQTT 명령을 파싱해 command handler로 전달한다.
    def handle_message(self, topic: str, payload: str) -> tuple[str, CommandAck]:
        topic_parts, command_message = parse_load_command(topic, payload, self.site_id)
        ack = self.handler.handle_command(
            device_id=topic_parts.device_id,
            payload={
                "command_id": command_message.command_id,
                "command_type": command_message.command_type,
                "payload": command_message.payload,
            },
        )
        return topic_parts.device_id, ack

    # MQTT 브로커 연결과 구독 루프를 시작한다.
    def start(self) -> None:
        if self.client is None:
            return
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            print(f"[LOAD][mqtt] subscriber connection skipped: {exc}")

    # 실행 중인 MQTT 구독 루프를 중단하고 연결을 닫는다.
    def stop(self) -> None:
        if self.client is None or not self.connected:
            return
        self.client.loop_stop()
        self.client.disconnect()

    # 연결이 열리면 load command wildcard 토픽을 구독한다.
    def _on_connect(self, client: Any, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = True
        topic = f"{self.site_id}/{self.resource_type}/+/command"
        client.subscribe(topic)

    # 수신 메시지를 처리하고 결과 ACK를 발행한다.
    def _on_message(self, _client: Any, _userdata: Any, message: InboundMqttMessage) -> None:
        payload = self._decode_payload(message.payload)
        device_id = self._extract_device_id(message.topic)
        try:
            device_id, ack = self.handle_message(message.topic, payload)
        except (ValueError, TypeError, JSONDecodeError, KeyError) as exc:
            ack = self._build_rejected_ack(payload, str(exc))
        self.publisher.publish_ack(self.site_id, RESOURCE_TYPE, device_id, ack)

    # 파싱 실패 시 사용할 rejected ACK를 생성한다.
    @staticmethod
    def _build_rejected_ack(payload: str, reason: str) -> CommandAck:
        command_id = "unknown"
        try:
            raw_payload = json.loads(payload)
            if isinstance(raw_payload, dict):
                command_id = str(raw_payload.get("command_id", command_id))
        except JSONDecodeError:
            pass
        return CommandAck(command_id=command_id, status="rejected", reason=reason)

    # MQTT payload 타입을 문자열로 정규화한다.
    @staticmethod
    def _decode_payload(payload: bytes | str) -> str:
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return payload

    # 토픽 문자열에서 대상 device_id를 뽑아낸다.
    @staticmethod
    def _extract_device_id(topic: str) -> str:
        parts = topic.split("/")
        if len(parts) >= 3:
            return parts[2]
        return "unknown"
