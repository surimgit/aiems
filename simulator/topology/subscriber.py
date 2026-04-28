from __future__ import annotations

import json
import threading
import time

import paho.mqtt.client as mqtt

import publisher
import service
from config import MQTT_HOST, MQTT_PORT
from state import _topology


def connect() -> None:
    def on_connect(client, userdata, flags, rc, props=None):
        print(f"[topology] MQTT connected (rc={rc})")
        plant_id = _topology.get("plant_id", "PLANT-ALPHA")
        cmd_topic = f"{plant_id}/switch/+/command"
        client.subscribe(cmd_topic)
        print(f"[topology] subscribed to {cmd_topic}")

    def on_message(client, userdata, message):
        topic = message.topic
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            return
        parts = topic.split("/")
        # {plant_id}/switch/{switch_id}/command
        if len(parts) == 4 and parts[1] == "switch" and parts[3] == "command":
            switch_id = parts[2]
            threading.Thread(
                target=service.handle_switch_command,
                args=(switch_id, payload),
                daemon=True,
            ).start()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()
            publisher.set_client(client)
            print(f"[topology] MQTT connected to {MQTT_HOST}:{MQTT_PORT}")
            return
        except Exception as e:
            print(f"[topology] MQTT connection failed: {e}. Retrying in 5s...")
            time.sleep(5)
