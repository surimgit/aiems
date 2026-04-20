import json
import paho.mqtt.client as mqtt
from typing import Callable

class DieselMQTTSubscriber:
    def __init__(self, client: mqtt.Client, plant_id: str, device_id: str):
        self.client = client
        self.command_topic = f"{plant_id}/diesel/{device_id}/command"
        self.on_command_callback: Callable[[dict], None] = None
        
        self.client.message_callback_add(self.command_topic, self._on_message)

    def set_command_callback(self, callback: Callable[[dict], None]):
        self.on_command_callback = callback

    def subscribe(self):
        self.client.subscribe(self.command_topic)
        print(f"Subscribed to {self.command_topic}")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if self.on_command_callback:
                self.on_command_callback(payload)
        except Exception as e:
            print(f"Error processing message on {msg.topic}: {e}")
