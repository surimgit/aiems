import asyncpg
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


_DEFAULTS = {
    "SOC_LOW": 20.0,
    "SOC_HIGH": 90.0,
    "DIESEL_START_SOC": 20.0,
    "DIESEL_STOP_NET_POWER": 10.0,
    "DIESEL_MIN_RUN_SECONDS": 300.0,
    "DIESEL_FUEL_CRITICAL": 5.0,
    "LOAD_SHED_DEFAULT_PRIORITY": 3.0,
    "LOAD_SHED_HOLD_SECONDS": 300.0,
    "ESS_POWER_LIMIT_KW": 50.0,
}


class PolicyReader:
    """control_policy 테이블에서 임계값을 읽어 캐시한다.
    refresh()를 주기적으로 호출해 DB 변경을 반영한다.
    """

    def __init__(self):
        self._pool: asyncpg.Pool | None = None
        self._cache: dict[str, float] = dict(_DEFAULTS)

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            host=DB_HOST, port=DB_PORT,
            database=DB_NAME, user=DB_USER, password=DB_PASSWORD,
            min_size=1, max_size=2,
        )
        await self.refresh()

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    async def refresh(self) -> None:
        if not self._pool:
            return
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM control_policy")
        for row in rows:
            self._cache[row["key"]] = float(row["value"])

    def get(self, key: str) -> float:
        return self._cache.get(key, _DEFAULTS.get(key, 0.0))
