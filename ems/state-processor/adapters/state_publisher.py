import json
import redis.asyncio as aioredis
from config import REDIS_HOST, REDIS_PORT, REDIS_STATE_STREAM, STATE_TTL_SECONDS


class StatePublisher:
    def __init__(self):
        self._client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    async def publish(self, snapshot: dict) -> None:
        key = f"state:{snapshot['site_id']}:{snapshot['device_id']}"
        value = json.dumps(snapshot, ensure_ascii=False)

        await self._client.set(key, value, ex=STATE_TTL_SECONDS)
        await self._client.xadd(REDIS_STATE_STREAM, {"data": value})

    async def close(self) -> None:
        await self._client.aclose()
