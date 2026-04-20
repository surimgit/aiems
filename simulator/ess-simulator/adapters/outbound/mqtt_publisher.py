from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from core.command_handler import CommandAck


class MqttPublisher:
    def __init__(self, broker_host: str, broker_port: int) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def build_topic(self, plant_id: str, device_id: str, message_type: str) -> str:
        return f"{plant_id}/ess/{device_id}/{message_type}"

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

    def serialize_telemetry(self, snapshot: dict[str, Any]) -> str:
        payload = {
            "device_id": snapshot["device_id"],
            "plant_id": snapshot["plant_id"],
            "resource_type": "ess",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "data": {
                "instantaneous": {
                    "P": snapshot["power_kw"],
                    "Q": 0.0,
                    "V": 380.0,
                    "I": 0.0,
                    "f": 60.0,
                    "PF": 1.0,
                },
                "energy": {
                    "kWh": snapshot["accumulated_energy_kwh"],
                    "kvarh": 0.0,
                },
                "status": {
                    "SOC": snapshot["soc"],
                    "operating_mode": snapshot["operating_mode"],
                    "comms_health": "ok",
                    "state": snapshot["state"],
                    "low_soc_threshold": snapshot["low_soc_threshold"],
                    "high_soc_threshold": snapshot["high_soc_threshold"],
                    "min_safe_soc_threshold": snapshot["min_safe_soc_threshold"],
                    "max_safe_soc_threshold": snapshot["max_safe_soc_threshold"],
                    "max_temperature_c": snapshot["max_temperature_c"],
                },
            },
        }
        return json.dumps(payload, ensure_ascii=False)

    def serialize_ack(self, ack: CommandAck) -> str:
        return ack.model_dump_json(exclude_none=True)

    def publish_telemetry(self, snapshot: dict[str, Any]) -> None:
        if not self.connected:
            return
        topic = self.build_topic(snapshot["plant_id"], snapshot["device_id"], "telemetry")
        self.client.publish(topic, self.serialize_telemetry(snapshot))

    def publish_ack(self, plant_id: str, device_id: str, ack: CommandAck) -> None:
        if not self.connected:
            return
        topic = self.build_topic(plant_id, device_id, "ack")
        self.client.publish(topic, self.serialize_ack(ack))

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        self.connected = True
        print(f"[ESS][mqtt] publisher connected to {self.broker_host}:{self.broker_port}")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any) -> None:
        self.connected = False
