import json
import uuid
from datetime import datetime, timezone

import asyncpg
import redis.asyncio as aioredis

from config import (
    REDIS_HOST, REDIS_PORT, SITE_ID,
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
)

STREAM_NORMAL = "ems:normal"
STREAM_EMERGENCY = "ems:emergency"


class EventPublisher:
    def __init__(self):
        self._redis = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
        self._pool = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            min_size=1, max_size=3,
        )

    async def publish(self, event: dict) -> None:
        severity = event.get("severity", "WARNING")
        stream = STREAM_EMERGENCY if severity == "CRITICAL" else STREAM_NORMAL

        envelope = {
            "event_id": f"evt-{uuid.uuid4().hex[:12]}",
            "site_id": SITE_ID,
            "device_id": event["device_id"],
            "resource_type": event["resource_type"],
            "event_type": event["event_type"],
            "severity": severity,
            "message": event.get("message", ""),
            "payload": event.get("payload", {}),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "control",
        }

        data = json.dumps(envelope, ensure_ascii=False)
        await self._redis.xadd(stream, {"data": data})

        print(f"[control][event] {severity} {event['event_type']} | {event['device_id']} | {event.get('message', '')}")

        if self._pool:
            await self._insert_db(envelope)

    async def _insert_db(self, envelope: dict) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO event_log
                    (time, site_id, device_id, resource_type, event_type, severity, message, payload)
                VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7)
                """,
                envelope["site_id"],
                envelope["device_id"],
                envelope["resource_type"].upper(),
                envelope["event_type"],
                envelope["severity"],
                envelope["message"],
                json.dumps(envelope["payload"]),
            )

    async def close(self) -> None:
        await self._redis.aclose()
        if self._pool:
            await self._pool.close()
