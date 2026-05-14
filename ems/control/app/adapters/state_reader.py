import json
import redis.asyncio as aioredis
from ..config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, SITE_ID


class StateReader:
    def __init__(self):
        self._client = aioredis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            password=REDIS_PASSWORD, decode_responses=True,
        )

    async def get_all(self) -> dict:
        pattern = f"state:{SITE_ID}:*"
        keys = [key async for key in self._client.scan_iter(pattern)]
        if not keys:
            return {}

        values = await self._client.mget(*keys)
        states = {}
        for key, value in zip(keys, values):
            if value:
                state = json.loads(value)
                device_id = state.get("device_id") or key.split(":")[-1]
                edge_id = state.get("edge_id")
                previous = states.get(device_id)
                if previous and previous.get("edge_id") != edge_id:
                    print(
                        "[control][state] duplicate device_id across edges: "
                        f"device={device_id} prev_edge={previous.get('edge_id')} edge={edge_id}. "
                        "Control command topic requires device_id to be unique per site."
                    )
                state.setdefault("state_key", key)
                states[device_id] = state
        return states

    async def close(self) -> None:
        await self._client.aclose()
