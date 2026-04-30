"""PostgreSQL state_write_db INSERT 게이트.

테이블:
  - device_meta       : 등록된 device 메타 + last_seen_at
  - comms_health_log  : 통신 두절/복구 이력
"""

import asyncpg
from datetime import datetime, timezone

from ..config import (
    STATE_DB_HOST, STATE_DB_PORT, STATE_DB_NAME, STATE_DB_USER, STATE_DB_PASSWORD,
)


def _parse_ts(ts: str | None) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


class PostgresWriter:
    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=STATE_DB_HOST, port=STATE_DB_PORT,
            database=STATE_DB_NAME, user=STATE_DB_USER, password=STATE_DB_PASSWORD,
            min_size=1, max_size=5,
        )
        print(f"[db-writer][postgres] 연결 완료 ({STATE_DB_HOST}:{STATE_DB_PORT}/{STATE_DB_NAME})")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── device_meta upsert ────────────────────────────────────────────────
    async def upsert_device_seen(self, snapshot: dict) -> None:
        """telemetry 수신 시 last_seen_at 갱신. 신규 device면 INSERT.

        snapshot 형식 (state-processor가 mg:state:result 에 발행):
            {
              "device_id": "solar-01",
              "site_id": "PLANT-ALPHA",
              "resource_type": "SOLAR",
              "timestamp": "...",
              "reported_state": {...},
              ...
            }
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO device_meta (device_id, site_id, resource_type, last_seen_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (device_id) DO UPDATE
                    SET last_seen_at = EXCLUDED.last_seen_at,
                        site_id      = EXCLUDED.site_id,
                        resource_type= EXCLUDED.resource_type
                """,
                snapshot["device_id"],
                snapshot.get("site_id"),
                snapshot.get("resource_type"),
                _parse_ts(snapshot.get("timestamp")),
            )

    # ── comms_health_log ──────────────────────────────────────────────────
    async def insert_comms_event(self, envelope: dict) -> None:
        """통신 상태 변화 이벤트.

        envelope 형식 (mg:db:write 에 publish):
            {
              "kind": "comms",
              "site_id": "...",
              "device_id": "...",
              "status": "ok" | "disconnected" | "wire_fault",
              "duration_sec": int | null,   # disconnected → ok 복구 시
              "timestamp": "ISO8601",
            }
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO comms_health_log (time, site_id, device_id, status, duration_sec)
                VALUES ($1, $2, $3, $4, $5)
                """,
                _parse_ts(envelope.get("timestamp")),
                envelope["site_id"],
                envelope["device_id"],
                envelope["status"],
                envelope.get("duration_sec"),
            )
