import json
import paho.mqtt.client as mqtt

class HeartbeatPublisher:
    def __init__(self, client: mqtt.Client, plant_id: str, device_id: str, resource_type: str = "solar"):
        self.client = client
        self.plant_id = plant_id
        self.device_id = device_id
        self.resource_type = resource_type
        self.heartbeat_topic = f"{plant_id}/heartbeat"

    def publish(self):
        heartbeat = {
            "device_id": self.device_id,
            "plant_id": self.plant_id,
            "resource_type": self.resource_type,
            "status": "online"
        }
        self.client.publish(self.heartbeat_topic, json.dumps(heartbeat))
