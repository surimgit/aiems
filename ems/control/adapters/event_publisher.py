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

# 알람 상태 Redis key prefix — 재시작해도 중복 발행 방지
_ALERTED_PREFIX = "ems:alerted:"
# 알람 TTL: 상태 지속 중 재발행 억제 시간 (초). 상태 회복 시 clear_alert()로 즉시 삭제.
_ALERTED_TTL_SEC = 3600


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

    async def is_alerted(self, alert_key: str) -> bool:
        """Redis에 알람 키가 존재하면 이미 발행된 상태."""
        return bool(await self._redis.exists(f"{_ALERTED_PREFIX}{alert_key}"))

    async def set_alerted(self, alert_key: str) -> None:
        """알람 발행 후 Redis에 키 등록 (TTL 설정)."""
        await self._redis.setex(f"{_ALERTED_PREFIX}{alert_key}", _ALERTED_TTL_SEC, "1")

    async def clear_alert(self, alert_key: str) -> None:
        """상태 회복 시 Redis 알람 키 삭제 — 다음 위반 시 재발행 허용."""
        await self._redis.delete(f"{_ALERTED_PREFIX}{alert_key}")

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
