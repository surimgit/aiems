from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any, Protocol

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from core.command_handler import CommandAck, CommandHandler
from mqtt_contract import parse_ess_command, to_simulator_command


class AckPublisher(Protocol):
    """Subscriber가 ACK 발행에 기대하는 최소 인터페이스다."""

    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        ...

    def serialize_ack(self, ack: CommandAck) -> str:
        ...


class InboundMqttMessage(Protocol):
    """실제 MQTT 메시지와 테스트 더블이 공통으로 맞춰야 할 형태다."""

    topic: str
    payload: bytes | str


class MqttCommandSubscriber:
    def __init__(
        self,
        command_handler: CommandHandler,
        publisher: AckPublisher,
        plant_id: str,
        resource_type: str,
        device_id: str,
        broker_host: str,
        broker_port: int,
    ) -> None:
        self.command_handler = command_handler
        self.publisher = publisher
        self.plant_id = plant_id
        self.resource_type = resource_type
        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False

    def handle_message(self, topic: str, payload: str) -> CommandAck:
        """수신한 command를 검증한 뒤 내부 handler에 전달한다."""

        _, command_message = parse_ess_command(topic, payload, self.plant_id, self.device_id)
        simulator_command = to_simulator_command(command_message)
        return self.command_handler.handle_command(simulator_command)

    def start(self) -> None:
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            print(f"[ESS][mqtt] subscriber connection skipped: {exc}")

    def stop(self) -> None:
        if self.connected:
            self.client.loop_stop()
            self.client.disconnect()

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = True
        topic = f"{self.plant_id}/{self.resource_type}/{self.device_id}/command"
        client.subscribe(topic)
        print(f"[ESS][mqtt] subscriber connected and subscribed to {topic}")

    def _on_message(self, _client: Any, _userdata: Any, message: InboundMqttMessage) -> None:
        """MQTT 콜백 진입점에서 ACK까지 한 번에 처리한다."""

        payload = self._decode_payload(message.payload)
        try:
            ack = self.handle_message(message.topic, payload)
        except (ValidationError, ValueError, TypeError, JSONDecodeError) as exc:
            ack = self._build_rejected_ack(payload, str(exc))

        self.publisher.publish_ack(self.plant_id, self.resource_type, self.device_id, ack)
        print(f"[ESS][mqtt][ack] {self.publisher.serialize_ack(ack)}")

    @staticmethod
    def _build_rejected_ack(payload: str, reason: str) -> CommandAck:
        """payload가 잘못돼도 command_id를 최대한 살려 rejected ACK를 만든다."""

        command_id = "unknown"
        try:
            raw_payload = json.loads(payload)
            if isinstance(raw_payload, dict):
                command_id = str(raw_payload.get("command_id", command_id))
        except JSONDecodeError:
            pass

        return CommandAck(
            command_id=command_id,
            status="rejected",
            reason=reason,
        )

    @staticmethod
    def _decode_payload(payload: bytes | str) -> str:
        """bytes 또는 str payload를 UTF-8 문자열로 통일한다."""

        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return payload
