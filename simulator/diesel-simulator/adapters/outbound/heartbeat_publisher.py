import json
import paho.mqtt.client as mqtt
from datetime import datetime, timezone

class HeartbeatPublisher:
    def __init__(self, client: mqtt.Client, plant_id: str, resource_type: str = "diesel"):
        self.client = client
        self.plant_id = plant_id
        self.resource_type = resource_type
        self.heartbeat_topic = f"{plant_id}/heartbeat"

    def publish(self, device_id: str):
        heartbeat = {
            "plant_id": self.plant_id,
            "resource_type": self.resource_type,
            "device_id": device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
            "status": "alive"
        }
        self.client.publish(self.heartbeat_topic, json.dumps(heartbeat))
