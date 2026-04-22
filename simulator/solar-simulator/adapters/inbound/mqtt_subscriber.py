import json
import paho.mqtt.client as mqtt
from typing import Callable

class SolarMQTTSubscriber:
    def __init__(self, client: mqtt.Client, plant_id: str):
        self.client = client
        self.plant_id = plant_id
        # 전체 태양광 디바이스의 명령을 와일드카드로 수신 (+ 사용)
        self.command_topic = f"{plant_id}/solar/+/command"
        self.on_command_callback: Callable[[str, dict], None] = None
        
        # 특정 토픽 패턴에 대한 메시지만 처리하도록 콜백 등록
        self.client.message_callback_add(self.command_topic, self._on_message)

    def set_command_callback(self, callback: Callable[[str, dict], None]):
        """콜백은 (target_device_id, payload) 형태여야 합니다."""
        self.on_command_callback = callback

    def subscribe(self):
        self.client.subscribe(self.command_topic)
        print(f"Subscribed to wildcard topic: {self.command_topic}")

    def _on_message(self, client, userdata, msg):
        try:
            # 토픽에서 device_id 파싱: PLANT-ALPHA/solar/solar-01/command -> solar-01
            topic_parts = msg.topic.split("/")
            if len(topic_parts) >= 4:
                target_device_id = topic_parts[2]
                payload = json.loads(msg.payload.decode())
                
                if self.on_command_callback:
                    self.on_command_callback(target_device_id, payload)
        except Exception as e:
            print(f"Error processing message on {msg.topic}: {e}")
