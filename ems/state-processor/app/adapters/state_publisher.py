import json
import redis.asyncio as aioredis
from ..config import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_STATE_STREAM
from ..realtime import emit_state_update


# 시뮬레이터 telemetry 주기(0.5~1s) 대비 충분한 여유.
# 이 시간 안에 갱신되지 않으면 해당 device state 자동 만료.
_STATE_TTL_SEC = 30


class StatePublisher:
    def __init__(self):
        self._client = aioredis.Redis(
            host=REDIS_HOST, port=REDIS_PORT,
            password=REDIS_PASSWORD, decode_responses=True,
        )

    async def publish(self, snapshot: dict) -> None:
        site_id = snapshot["site_id"]
        device_id = snapshot["device_id"]
        edge_id = snapshot.get("edge_id") or device_id

        # desired_state — control이 저장한 키에서 읽어 병합
        desired_raw = await self._get_desired(site_id, edge_id, device_id)
        if desired_raw:
            desired = json.loads(desired_raw)
            snapshot["desired_state"] = desired.get("payload")
            snapshot["last_command_id"] = desired.get("command_id")
        else:
            snapshot["desired_state"] = None
            snapshot["last_command_id"] = None

        key = _state_key(site_id, edge_id, device_id)
        snapshot["state_key"] = key
        value = json.dumps(snapshot, ensure_ascii=False)

        await self._client.set(key, value, ex=_STATE_TTL_SEC)
        await self._client.xadd(REDIS_STATE_STREAM, {"data": value})
        emit_state_update(snapshot)

    async def _get_desired(self, site_id: str, edge_id: str, device_id: str) -> str | None:
        keys = []
        if edge_id and edge_id != device_id:
            keys.append(f"desired:{site_id}:{edge_id}:{device_id}")
        keys.append(f"desired:{site_id}:{device_id}")

        values = await self._client.mget(*keys)
        for value in values:
            if value:
                return value
        return None

    async def close(self) -> None:
        await self._client.aclose()


def _state_key(site_id: str, edge_id: str, device_id: str) -> str:
    if edge_id and edge_id != device_id:
        return f"state:{site_id}:{edge_id}:{device_id}"
    return f"state:{site_id}:{device_id}"
