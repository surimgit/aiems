import json
import redis.asyncio as aioredis
from config import REDIS_HOST, REDIS_PORT, STREAM_MAXLEN


class RedisPublisher:
    def __init__(self):
        self._client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    async def publish(self, stream: str, message: dict) -> None:
        await self._client.xadd(
            stream,
            {"data": json.dumps(message, ensure_ascii=False)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )

    async def close(self) -> None:
        await self._client.aclose()
