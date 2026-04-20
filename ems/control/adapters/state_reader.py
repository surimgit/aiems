import json
import redis.asyncio as aioredis
from config import REDIS_HOST, REDIS_PORT, SITE_ID


class StateReader:
    def __init__(self):
        self._client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    async def get_all(self) -> dict:
        pattern = f"state:{SITE_ID}:*"
        keys = await self._client.keys(pattern)
        if not keys:
            return {}

        values = await self._client.mget(*keys)
        states = {}
        for key, value in zip(keys, values):
            if value:
                device_id = key.split(":")[-1]
                states[device_id] = json.loads(value)
        return states

    async def close(self) -> None:
        await self._client.aclose()
