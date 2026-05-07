from __future__ import annotations

import json
import os
from json import JSONDecodeError
from typing import Callable
from typing import Any, Protocol

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from core.command_handler import CommandAck, CommandHandler
from mqtt_contract import parse_ess_command, to_simulator_command


class AckPublisher(Protocol):
    def publish_ack(self, plant_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        ...

    def serialize_ack(self, ack: CommandAck) -> str:
        ...


class InboundMqttMessage(Protocol):
    topic: str
    payload: bytes | str


class MqttCommandSubscriber:
    def __init__(
        self,
        command_handlers: dict[str, CommandHandler],
        publisher: AckPublisher,
        plant_id: str,
        resource_type: str,
        broker_host: str,
        broker_port: int,
        topology_callback=None,
    ) -> None:
        self.command_handlers = command_handlers
        self.publisher = publisher
        self.plant_id = plant_id
        self.resource_type = resource_type
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topology_callback = topology_callback
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        # MQTT 인증 (broker 인증 필수일 때) — env 비면 anonymous
        _mqtt_user = os.getenv("MQTT_USER")
        _mqtt_pw = os.getenv("MQTT_PASSWORD")
        if _mqtt_user:
            self.client.username_pw_set(_mqtt_user, _mqtt_pw)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False

    def handle_message(self, topic: str, payload: str) -> tuple[str, CommandAck]:
        topic_parts, command_message = parse_ess_command(topic, payload, self.plant_id)
        handler = self.command_handlers[topic_parts.device_id]
        simulator_command = to_simulator_command(command_message)
        return topic_parts.device_id, handler.handle_command(simulator_command)

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
        topic = f"{self.plant_id}/{self.resource_type}/+/command"
        client.subscribe(topic)
        print(f"[ESS][mqtt] subscriber connected and subscribed to {topic}")
        topology_topic = f"{self.plant_id}/topology/#"
        client.subscribe(topology_topic)
        print(f"[ESS][mqtt] subscribed to topology: {topology_topic}")

    def _on_message(self, _client: Any, _userdata: Any, message: InboundMqttMessage) -> None:
        if "/topology/" in message.topic:
            if self.topology_callback is not None:
                try:
                    payload = json.loads(self._decode_payload(message.payload))
                    self.topology_callback(message.topic, payload)
                except Exception:
                    pass
            return
        payload = self._decode_payload(message.payload)
        device_id = self._extract_device_id(message.topic)
        try:
            device_id, ack = self.handle_message(message.topic, payload)
        except (ValidationError, ValueError, TypeError, JSONDecodeError, KeyError) as exc:
            ack = self._build_rejected_ack(payload, str(exc))
        self.publisher.publish_ack(self.plant_id, self.resource_type, device_id, ack)
        print(f"[ESS][mqtt][{device_id}][ack] {self.publisher.serialize_ack(ack)}")

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

    @staticmethod
    def _decode_payload(payload: bytes | str) -> str:
        if isinstance(payload, bytes):
            return payload.decode("utf-8")
        return payload

    @staticmethod
    def _extract_device_id(topic: str) -> str:
        parts = topic.split("/")
        if len(parts) >= 3:
            return parts[2]
        return "unknown"
