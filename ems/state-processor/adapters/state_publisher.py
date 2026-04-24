import json
import redis.asyncio as aioredis
from config import REDIS_HOST, REDIS_PORT, REDIS_STATE_STREAM


class StatePublisher:
    def __init__(self):
        self._client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    async def publish(self, snapshot: dict) -> None:
        site_id = snapshot["site_id"]
        device_id = snapshot["device_id"]

        # desired_state — control이 저장한 키에서 읽어 병합
        desired_raw = await self._client.get(f"desired:{site_id}:{device_id}")
        if desired_raw:
            desired = json.loads(desired_raw)
            snapshot["desired_state"] = desired.get("payload")
            snapshot["last_command_id"] = desired.get("command_id")
        else:
            snapshot["desired_state"] = None
            snapshot["last_command_id"] = None

        key = f"state:{site_id}:{device_id}"
        value = json.dumps(snapshot, ensure_ascii=False)

        await self._client.set(key, value)
        await self._client.xadd(REDIS_STATE_STREAM, {"data": value})

    async def close(self) -> None:
        await self._client.aclose()
