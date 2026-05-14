"""state-processor stream consumer.

책임 (DB Writer 단일 게이트 정책 이후 단순화):
  - mg:sensor:data 를 받아 calculate()로 device 상태 스냅샷 계산
  - 스냅샷을 Redis state cache 에 publish (대시보드 실시간 조회용)
  - 스냅샷을 mg:state:result 로 발행 (db-writer 가 sensor_data 집계 + device_meta upsert)

DB INSERT 는 db-writer 가 모두 담당. state-processor 는 stream publish 만.
emergency 는 db-writer 가 직접 mg:emergency:event 를 consume — 여기서 처리 안 함.
"""

import asyncio
import json

import redis.asyncio as aioredis

from ..config import (
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
    REDIS_NORMAL_STREAM, REDIS_STATE_STREAM,
    CONSUMER_GROUP, CONSUMER_NAME,
)
from ..domain.state_calculator import calculate
from .state_publisher import StatePublisher


async def _ensure_group(client: aioredis.Redis, stream: str) -> None:
    try:
        await client.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"[state-processor] consumer group 생성: {CONSUMER_GROUP} / {stream}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            raise


async def _consume_normal(client: aioredis.Redis, publisher: StatePublisher) -> None:
    """mg:sensor:data → calculate → Redis state cache + mg:state:result publish."""
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
                    # control 발 WARNING/INFO 이벤트는 telemetry 스키마가 아니므로 skip.
                    # — calculate() 결과 None-filled snapshot 이 state cache 를 오염시키는 것 방지.
                    if envelope.get("source") == "control":
                        await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                        continue
                    snapshot = calculate(envelope)
                    if snapshot is None:
                        await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                        continue
                    # 1) Redis state cache 갱신 (실시간 조회용)
                    # 2) mg:state:result 로 발행 — db-writer 가 받아서 sensor_data 집계 + device_meta upsert
                    await publisher.publish(snapshot)
                    await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                    print(f"[state-processor] {snapshot['device_id']} ({snapshot['resource_type']}) → {REDIS_STATE_STREAM}")
                except Exception as e:
                    print(f"[state-processor] 처리 실패 id={msg_id} error={e}")


async def run(publisher: StatePublisher) -> None:
    client = aioredis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASSWORD, decode_responses=True,
    )
    await _ensure_group(client, REDIS_NORMAL_STREAM)

    await _consume_normal(client, publisher)
