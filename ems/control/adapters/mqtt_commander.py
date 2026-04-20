import json
import uuid
import aiomqtt
from config import MQTT_HOST, MQTT_PORT, SITE_ID


class MqttCommander:
    def __init__(self):
        self._client = None

    async def __aenter__(self):
        self._client = aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._client.__aexit__(*args)

    async def send(self, command: dict) -> None:
        device_id = command["device_id"]
        resource_type = command["resource_type"]
        topic = f"{SITE_ID}/{resource_type}/{device_id}/command"
        payload = {
            "command_id": f"cmd-{uuid.uuid4().hex[:8]}",
            "command_type": command["command_type"],
            "payload": command["payload"],
        }
        await self._client.publish(topic, json.dumps(payload, ensure_ascii=False))
        print(f"[control] → {topic} | {command['command_type']} {command['payload']} | {command['reason']}")
