import json
import uuid
import aiomqtt
from config import MQTT_HOST, MQTT_PORT, SITE_ID
from adapters.db_writer import ControlDBWriter


class MqttCommander:
    def __init__(self, db: ControlDBWriter):
        self._client = None
        self._db = db

    async def __aenter__(self):
        self._client = aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *args):
        await self._client.__aexit__(*args)

    async def send(self, command: dict) -> None:
        device_id = command["device_id"]
        resource_type = command["resource_type"]
        command_id = str(uuid.uuid4())
        topic = f"{SITE_ID}/{resource_type}/{device_id}/command"
        payload = {
            "command_id": command_id,
            "command_type": command["command_type"],
            "payload": command["payload"],
        }
        await self._client.publish(topic, json.dumps(payload, ensure_ascii=False))
        print(f"[control] → {topic} | {command['command_type']} {command['payload']} | {command['reason']}")

        command["site_id"] = SITE_ID
        await self._db.insert_command(command, command_id)
