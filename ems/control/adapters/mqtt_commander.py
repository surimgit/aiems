import asyncio
import json
import time
import uuid

import aiomqtt

from config import MQTT_HOST, MQTT_PORT, SITE_ID
from adapters.db_writer import ControlDBWriter

_ACK_TIMEOUT_SEC = 30.0


class MqttCommander:
    def __init__(self, db: ControlDBWriter):
        self._client = None
        self._db = db
        # command_id → (sent_at, device_id, resource_type)
        self._pending_acks: dict[str, tuple[float, str, str]] = {}
        self._ack_task: asyncio.Task | None = None

    async def __aenter__(self):
        self._client = aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT)
        await self._client.__aenter__()
        # ACK 토픽 구독
        await self._client.subscribe(f"{SITE_ID}/+/+/ack")
        self._ack_task = asyncio.create_task(self._ack_listener())
        asyncio.create_task(self._timeout_checker())
        return self

    async def __aexit__(self, *args):
        if self._ack_task:
            self._ack_task.cancel()
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
            "source": command.get("issued_by", "rule"),
            "expires_in_sec": command.get("expires_in_sec", 30),
            "force": command.get("force", False),
        }
        await self._client.publish(topic, json.dumps(payload, ensure_ascii=False))
        print(f"[control] → {topic} | {command['command_type']} {command['payload']} | {command['reason']}")

        command["site_id"] = SITE_ID
        await self._db.insert_command(command, command_id)

        # ACK 대기 목록에 등록
        self._pending_acks[command_id] = (time.monotonic(), device_id, resource_type)

    async def _ack_listener(self) -> None:
        try:
            async for msg in self._client.messages:
                topic = str(msg.topic)
                if not topic.endswith("/ack"):
                    continue
                try:
                    data = json.loads(msg.payload)
                    command_id = data.get("command_id")
                    status = data.get("status", "unknown")
                    reason = data.get("reason", "")
                    if command_id and command_id in self._pending_acks:
                        _, device_id, _ = self._pending_acks.pop(command_id)
                        ack_label = f"{status}" + (f" ({reason})" if reason else "")
                        print(f"[control][ack] {device_id} | {command_id[:8]}... | {ack_label}")
                        await self._db.update_ack(command_id, status.upper())
                except Exception:
                    continue
        except asyncio.CancelledError:
            pass

    async def _timeout_checker(self) -> None:
        while True:
            await asyncio.sleep(5)
            now = time.monotonic()
            expired = [
                cid for cid, (sent_at, _, __) in self._pending_acks.items()
                if now - sent_at > _ACK_TIMEOUT_SEC
            ]
            for command_id in expired:
                _, device_id, _ = self._pending_acks.pop(command_id)
                print(f"[control][ack] TIMEOUT | {device_id} | {command_id[:8]}...")
                await self._db.update_ack(command_id, "TIMEOUT")
