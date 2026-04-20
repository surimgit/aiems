import json
import redis.asyncio as aioredis
from config import (
    REDIS_HOST, REDIS_PORT,
    REDIS_NORMAL_STREAM, CONSUMER_GROUP, CONSUMER_NAME,
)
from domain.state_calculator import calculate
from adapters.state_publisher import StatePublisher


async def _ensure_group(client: aioredis.Redis) -> None:
    try:
        await client.xgroup_create(REDIS_NORMAL_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"[state-processor] consumer group 생성: {CONSUMER_GROUP}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            print(f"[state-processor] consumer group 이미 존재: {CONSUMER_GROUP}")
        else:
            raise


async def run(publisher: StatePublisher) -> None:
    client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    await _ensure_group(client)
    print(f"[state-processor] {REDIS_NORMAL_STREAM} 구독 시작")

    while True:
        results = await client.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=CONSUMER_NAME,
            streams={REDIS_NORMAL_STREAM: ">"},
            count=100,
            block=1000,
        )
        if not results:
            continue

        for _, messages in results:
            for msg_id, fields in messages:
                try:
                    envelope = json.loads(fields["data"])
                    snapshot = calculate(envelope)
                    await publisher.publish(snapshot)
                    await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                    print(f"[state-processor] {snapshot['device_id']} ({snapshot['resource_type']}) → ems:state")
                except Exception as e:
                    print(f"[state-processor] 처리 실패 id={msg_id} error={e}")
