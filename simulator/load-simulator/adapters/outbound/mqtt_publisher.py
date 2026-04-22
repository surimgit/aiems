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

    @staticmethod
    def build_topic(site_id: str, resource_type: str, device_id: str, message_type: str) -> str:
        return build_topic(site_id, resource_type, device_id, message_type)

    @staticmethod
    def serialize_telemetry(device: LoadDevice) -> str:
        return json.dumps(snapshot_to_telemetry(device), separators=(",", ":"))

    @staticmethod
    def serialize_ack(ack: CommandAck) -> str:
        return json.dumps(ack_to_payload(ack), separators=(",", ":"))

    @staticmethod
    def serialize_heartbeat(site_id: str, device_id: str) -> str:
        return serialize_heartbeat(site_id, device_id)

    def start(self) -> None:
        if self.client is None:
            return
        try:
            self.client.connect(self.broker_host, self.broker_port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            print(f"[LOAD][mqtt] publisher connection skipped: {exc}")

    def stop(self) -> None:
        if self.client is None or not self.connected:
            return
        self.client.loop_stop()
        self.client.disconnect()

    def publish_telemetry(self, device: LoadDevice) -> None:
        if self.client is None or not self.connected:
            return
        topic = self.build_topic(device.site_id, RESOURCE_TYPE, device.device_id, "telemetry")
        self.client.publish(topic, self.serialize_telemetry(device), qos=1)

    def publish_ack(self, site_id: str, resource_type: str, device_id: str, ack: CommandAck) -> None:
        if self.client is None or not self.connected:
            return
        topic = self.build_topic(site_id, resource_type, device_id, "ack")
        self.client.publish(topic, self.serialize_ack(ack), qos=1)

    def publish_heartbeat(self, site_id: str, resource_type: str, device_id: str) -> None:
        if self.client is None or not self.connected:
            return
        topic = resolve_heartbeat_topic(site_id)
        self.client.publish(topic, self.serialize_heartbeat(site_id, device_id), qos=1)

    def _on_connect(self, _client: Any, _userdata: Any, _flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = True

    def _on_disconnect(self, _client: Any, _userdata: Any, _disconnect_flags: Any, _reason_code: Any, _properties: Any) -> None:
        self.connected = False
