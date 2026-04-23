import json
import asyncpg
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


class ControlDBWriter:
    def __init__(self):
        self._pool = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            min_size=1, max_size=3,
        )
        print("[control] TimescaleDB 연결 완료")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def get_command(self, command_id: str) -> tuple | None:
        """(command_type, payload) 반환. 없으면 None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT command_type, payload FROM control_history WHERE command_id = $1::uuid",
                command_id,
            )
        if not row:
            return None
        return row["command_type"], row["payload"]

    async def mark_verified(self, command_id: str, verified: bool) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                "UPDATE control_history SET verified = $1 WHERE command_id = $2::uuid",
                verified, command_id,
            )

    async def update_ack(self, command_id: str, status: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE control_history
                SET ack_status = $1, ack_time = NOW()
                WHERE command_id = $2::uuid
                """,
                status, command_id,
            )

    async def insert_command(self, command: dict, command_id: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO control_history
                    (time, command_id, site_id, device_id, resource_type,
                     command_type, payload, reason, issued_by)
                VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8)
                """,
                command_id,
                command.get("site_id", "PLANT-ALPHA"),
                command["device_id"],
                command["resource_type"].upper(),
                command["command_type"],
                json.dumps(command["payload"]),
                command.get("reason", ""),
                command.get("issued_by", "rule"),
            )
