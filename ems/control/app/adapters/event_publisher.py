"""control 의 이벤트 발행자.

DB Writer 단일 게이트 정책 이후 — 이 모듈은 DB 에 직접 INSERT 하지 않는다.
모든 이벤트는 Redis stream 으로 발행, db-writer 가 받아 event_log INSERT.

발행 stream 분기:
  - severity == CRITICAL → mg:emergency:event  (db-writer 가 즉시 INSERT)
  - 그 외 (WARNING/INFO) → mg:db:write (kind=event, db-writer 가 INSERT)
"""

import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis

from ..config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, SITE_ID

STREAM_EMERGENCY = "mg:emergency:event"
STREAM_DB_WRITE = "mg:db:write"

# 알람 상태 Redis key prefix — 재시작해도 중복 발행 방지
_ALERTED_PREFIX = "ems:alerted:"
# 알람 TTL: 상태 지속 중 재발행 억제 시간 (초). 상태 회복 시 clear_alert()로 즉시 삭제.
_ALERTED_TTL_SEC = 3600


class EventPublisher:
    def __init__(self):
        self._redis = aioredis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            password=REDIS_PASSWORD, decode_responses=True,
        )

    async def connect(self) -> None:
        # DB pool 더 이상 만들지 않음 (db-writer 단일 게이트)
        pass

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
        envelope = {
            "event_id": f"evt-{uuid.uuid4().hex[:12]}",
            "site_id": SITE_ID,
            "edge_id": event.get("edge_id"),
            "device_id": event["device_id"],
            "resource_type": event["resource_type"].upper(),
            "event_type": event["event_type"],
            "severity": severity,
            "message": event.get("message", ""),
            "payload": event.get("payload", {}),
            "location": event.get("location"),
            "latitude": event.get("latitude"),
            "longitude": event.get("longitude"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "control",
        }
        envelope = {key: value for key, value in envelope.items() if value is not None}
        data = json.dumps(envelope, ensure_ascii=False)

        if severity == "CRITICAL":
            await self._redis.xadd(STREAM_EMERGENCY, {"data": data})
        else:
            # WARNING/INFO 는 db-writer 가 mg:db:write 에서 받아 event_log INSERT
            envelope_with_kind = dict(envelope)
            envelope_with_kind["kind"] = "event"
            await self._redis.xadd(STREAM_DB_WRITE, {"data": json.dumps(envelope_with_kind, ensure_ascii=False)})

        print(f"[control][event] {severity} {event['event_type']} | {event['device_id']} | {event.get('message', '')}")

    async def close(self) -> None:
        await self._redis.aclose()
