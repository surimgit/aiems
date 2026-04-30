"""TimescaleDB INSERT 게이트.

테이블:
  - sensor_data       : 1초 batch 집계 (WindowAggregator 결과)
  - event_log         : 긴급 이벤트
  - control_history   : 제어 명령 이력 (이번 단계는 envelope 받아 INSERT)
"""

import json
import asyncpg
from datetime import datetime, timezone

from ..config import (
    TIMESCALE_HOST, TIMESCALE_PORT, TIMESCALE_DB, TIMESCALE_USER, TIMESCALE_PASSWORD,
)


def _parse_ts(ts: str | None) -> datetime:
    """ISO8601 문자열을 timezone-aware datetime 으로 변환. 실패 시 현재 UTC."""
    if not ts:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


class TimescaleWriter:
    def __init__(self):
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=TIMESCALE_HOST, port=TIMESCALE_PORT,
            database=TIMESCALE_DB, user=TIMESCALE_USER, password=TIMESCALE_PASSWORD,
            min_size=1, max_size=5,
        )
        print(f"[db-writer][timescale] 연결 완료 ({TIMESCALE_HOST}:{TIMESCALE_PORT}/{TIMESCALE_DB})")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── sensor_data ───────────────────────────────────────────────────────
    async def insert_sensor_batch(self, rows: list[dict]) -> None:
        """1초 집계 결과 batch INSERT. WindowAggregator.flush() 결과를 그대로 받는다."""
        if not rows:
            return
        async with self._pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO sensor_data
                    (time, site_id, device_id, resource_type,
                     p_avg, p_max, p_min, q_avg, v_avg, f_avg, pf_avg, soc, sample_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                [
                    (
                        _parse_ts(r["time"]), r["site_id"], r["device_id"], r["resource_type"],
                        r.get("p_avg"), r.get("p_max"), r.get("p_min"),
                        r.get("q_avg"), r.get("v_avg"), r.get("f_avg"), r.get("pf_avg"),
                        r.get("soc"), r.get("sample_count", 1),
                    )
                    for r in rows
                ],
            )

    # ── event_log ─────────────────────────────────────────────────────────
    async def insert_event(self, envelope: dict) -> None:
        """긴급 이벤트 INSERT. mg:emergency:event 의 envelope 그대로 받음."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO event_log
                    (time, site_id, device_id, resource_type,
                     event_type, severity, message, payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                _parse_ts(envelope.get("timestamp")),
                envelope.get("site_id"),
                envelope.get("device_id") or envelope.get("resource_id"),
                envelope.get("resource_type"),
                envelope.get("event_type", "EVT-E-000"),
                envelope.get("severity", "EMERGENCY"),
                envelope.get("message", ""),
                json.dumps(envelope.get("payload", {}), ensure_ascii=False),
            )

    # ── control_history ──────────────────────────────────────────────────
    async def insert_command(self, envelope: dict) -> None:
        """제어 명령 이력 INSERT. mg:db:write 에 control이 보낸 command_result envelope.

        envelope 형식:
            {
              "kind": "command",
              "command_id": "uuid",
              "site_id": "...",
              "device_id": "...",
              "resource_type": "...",
              "command_type": "...",
              "payload": {...},
              "reason": "...",
              "issued_by": "rule|operator|ai",
              "ack_status": "pending|accepted|rejected|timeout",
              "ack_time": "ISO8601 or null",
              "verified": null|true|false,
              "timestamp": "ISO8601",
            }
        """
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO control_history
                    (time, command_id, site_id, device_id, resource_type,
                     command_type, payload, reason, issued_by, ack_status, ack_time, verified)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                _parse_ts(envelope.get("timestamp")),
                envelope["command_id"],
                envelope["site_id"],
                envelope["device_id"],
                envelope["resource_type"],
                envelope["command_type"],
                json.dumps(envelope.get("payload", {}), ensure_ascii=False),
                envelope.get("reason"),
                envelope.get("issued_by", "rule"),
                envelope.get("ack_status", "pending"),
                _parse_ts(envelope["ack_time"]) if envelope.get("ack_time") else None,
                envelope.get("verified"),
            )

    async def update_command_ack(self, command_id: str, ack_status: str, verified: bool | None = None) -> None:
        """폐루프 검증 결과로 control_history UPDATE.
        압축된 chunk(30d 이상) 는 UPDATE 실패 가능 — A안 정책.
        """
        async with self._pool.acquire() as conn:
            if verified is None:
                await conn.execute(
                    "UPDATE control_history SET ack_status=$1, ack_time=NOW() WHERE command_id=$2",
                    ack_status, command_id,
                )
            else:
                await conn.execute(
                    "UPDATE control_history SET ack_status=$1, ack_time=NOW(), verified=$2 WHERE command_id=$3",
                    ack_status, verified, command_id,
                )
