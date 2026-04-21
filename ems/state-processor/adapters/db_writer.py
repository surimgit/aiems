import json
import asyncpg
from datetime import datetime, timezone
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def _parse_ts(ts: str | None) -> datetime:
    if not ts:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


class DBWriter:
    def __init__(self):
        self._pool = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            min_size=1, max_size=5,
        )
        print("[db-writer] TimescaleDB 연결 완료")

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def insert_sensor_batch(self, rows: list[dict]) -> None:
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

    async def insert_event(self, snapshot: dict, event_type: str, severity: str, message: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO event_log
                    (time, site_id, device_id, resource_type, event_type, severity, message, payload)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                _parse_ts(snapshot.get("timestamp")),
                snapshot["site_id"],
                snapshot["device_id"],
                snapshot["resource_type"],
                event_type,
                severity,
                message,
                json.dumps(snapshot.get("reported_state", {})),
            )
