"""control 의 DB write 어댑터.

DB Writer 단일 게이트 정책 이후 — control 은 DB 에 직접 INSERT/UPDATE 하지 않는다.
모든 write 는 mg:db:write stream 으로 publish, db-writer 가 받아 INSERT.

읽기는 별도 외부 connection 사용 (mqtt_commander 폐루프 검증용 SELECT).
이 파일은 그 둘을 묶어서 제공한다:
  - ControlDBWriter (이름 호환 유지) :
      • insert_command(envelope, command_id) → stream publish
      • update_ack(command_id, status)        → stream publish
      • mark_verified(command_id, verified)   → stream publish
      • get_command(command_id)              → TimescaleDB SELECT (외부 connection)
"""

import json
import asyncpg
import redis.asyncio as aioredis

from ..config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
)

STREAM_DB_WRITE = "mg:db:write"


class ControlDBWriter:
    """control 의 DB 인터페이스. write 는 stream, read 는 직접 connection."""

    def __init__(self):
        self._pool: asyncpg.Pool | None = None
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        # SELECT 용 TimescaleDB pool (control_history 폐루프 검증)
        self._pool = await asyncpg.create_pool(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            min_size=1, max_size=3,
        )
        # write 용 Redis stream client
        self._redis = aioredis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            password=REDIS_PASSWORD, decode_responses=True,
        )
        print("[control][db] TimescaleDB(SELECT) + Redis(stream publish) 연결 완료")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
        if self._redis:
            await self._redis.aclose()

    # ── READ (직접 connection) ─────────────────────────────────────────────
    async def get_command(self, command_id: str) -> tuple | None:
        """(command_type, payload) 반환. 없으면 None.
        폐루프 검증 시 mqtt_commander 가 사용.
        """
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT command_type, payload FROM control_history WHERE command_id = $1::uuid",
                command_id,
            )
        if not row:
            return None
        return row["command_type"], row["payload"]

    # ── WRITE (모두 stream publish) ────────────────────────────────────────
    async def insert_command(self, command: dict, command_id: str) -> None:
        """rule engine 이 발행한 명령을 control_history 에 기록 요청.
        실제 INSERT 는 db-writer 가 mg:db:write 받아서 수행.
        """
        envelope = {
            "kind": "command",
            "command_id": command_id,
            "site_id": command.get("site_id", "PLANT-ALPHA"),
            "device_id": command["device_id"],
            "resource_type": command["resource_type"].upper(),
            "command_type": command["command_type"],
            "payload": command["payload"],
            "reason": command.get("reason", ""),
            "issued_by": command.get("issued_by", "rule"),
            "ack_status": "pending",
        }
        await self._redis.xadd(STREAM_DB_WRITE, {"data": json.dumps(envelope, ensure_ascii=False)})

    async def update_ack(self, command_id: str, status: str) -> None:
        """ACK 수신 시 control_history.ack_status 갱신 요청."""
        envelope = {
            "kind": "command",
            "update_ack": True,
            "command_id": command_id,
            "ack_status": status,
        }
        await self._redis.xadd(STREAM_DB_WRITE, {"data": json.dumps(envelope, ensure_ascii=False)})

    async def mark_verified(self, command_id: str, verified: bool) -> None:
        """폐루프 검증 결과로 control_history.verified 갱신 요청."""
        envelope = {
            "kind": "command",
            "update_ack": True,
            "command_id": command_id,
            "ack_status": "accepted",   # verify 단계는 이미 accepted 상태
            "verified": verified,
        }
        await self._redis.xadd(STREAM_DB_WRITE, {"data": json.dumps(envelope, ensure_ascii=False)})
