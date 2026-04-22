import json
import paho.mqtt.client as mqtt
from domain.edge.models import TelemetryMessage, EventMessage, CommandAckMessage

class DieselMQTTPublisher:
    def __init__(self, client: mqtt.Client, plant_id: str):
        self.client = client
        self.plant_id = plant_id

    def _get_base_topic(self, device_id: str) -> str:
        return f"{self.plant_id}/diesel/{device_id}"

    def publish_telemetry(self, telemetry: TelemetryMessage):
        topic = f"{self._get_base_topic(telemetry.device_id)}/telemetry"
        self.client.publish(topic, telemetry.json())

    def publish_event(self, event: EventMessage):
        # 명세서: 비상 상황(EMERGENCY severity)은 emergency 토픽으로 분기
        base_topic = self._get_base_topic(event.device_id)
        target_topic = f"{base_topic}/emergency" if event.severity == "EMERGENCY" else f"{base_topic}/event"
        self.client.publish(target_topic, event.json())

    def publish_ack(self, device_id: str, ack: CommandAckMessage):
        # Ack는 파라미터로 받은 device_id를 통해 전송
        topic = f"{self._get_base_topic(device_id)}/ack"
        self.client.publish(topic, ack.json())
