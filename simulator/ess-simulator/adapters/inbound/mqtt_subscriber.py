from __future__ import annotations

import json
from typing import Any

import paho.mqtt.client as mqtt

from adapters.outbound.mqtt_publisher import MqttPublisher
from core.command_handler import CommandAck, CommandHandler


class MqttCommandSubscriber:
    def __init__(
        self,
        command_handler: CommandHandler,
        publisher: MqttPublisher,
        plant_id: str,
        device_id: str,
        broker_host: str,
        broker_port: int,
    ) -> None:
        self.command_handler = command_handler
        self.publisher = publisher
        self.plant_id = plant_id
        self.device_id = device_id
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.connected = False

    def handle_message(self, topic: str, payload: str) -> CommandAck:
        parts = topic.split("/")
        if len(parts) != 4 or parts[-1] != "command":
            raise ValueError(f"Invalid command topic: {topic}")

        raw_command = json.loads(payload)
        return self.command_handler.handle_command(raw_command)

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

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        self.connected = True
        topic = f"{self.plant_id}/ess/{self.device_id}/command"
        client.subscribe(topic)
        print(f"[ESS][mqtt] subscriber connected and subscribed to {topic}")

    def _on_message(self, client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
        ack = self.handle_message(message.topic, message.payload.decode("utf-8"))
        self.publisher.publish_ack(self.plant_id, self.device_id, ack)
        print(f"[ESS][mqtt][ack] {self.publisher.serialize_ack(ack)}")
