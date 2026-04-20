import json
import paho.mqtt.client as mqtt
from core.models import TelemetryMessage, EventMessage, CommandAckMessage

class DieselMQTTPublisher:
    def __init__(self, client: mqtt.Client, plant_id: str, device_id: str):
        self.client = client
        self.plant_id = plant_id
        self.device_id = device_id
        
        self.base_topic = f"{plant_id}/diesel/{device_id}"
        self.telemetry_topic = f"{self.base_topic}/telemetry"
        self.event_topic = f"{self.base_topic}/event"
        self.emergency_topic = f"{self.base_topic}/emergency"
        self.ack_topic = f"{self.base_topic}/ack"

    def publish_telemetry(self, telemetry: TelemetryMessage):
        self.client.publish(self.telemetry_topic, telemetry.json())

    def publish_event(self, event: EventMessage):
        target_topic = self.emergency_topic if event.severity == "EMERGENCY" else self.event_topic
        self.client.publish(target_topic, event.json())

    def publish_ack(self, ack: CommandAckMessage):
        self.client.publish(self.ack_topic, ack.json())
