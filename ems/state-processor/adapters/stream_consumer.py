import asyncio
import json
import redis.asyncio as aioredis
from config import (
    REDIS_HOST, REDIS_PORT,
    REDIS_NORMAL_STREAM, REDIS_EMERGENCY_STREAM,
    CONSUMER_GROUP, CONSUMER_NAME,
)
from domain.state_calculator import calculate
from domain.aggregator import WindowAggregator
from adapters.state_publisher import StatePublisher
from adapters.db_writer import DBWriter


async def _ensure_group(client: aioredis.Redis, stream: str) -> None:
    try:
        await client.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"[state-processor] consumer group 생성: {CONSUMER_GROUP} / {stream}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            raise


async def _consume_normal(client: aioredis.Redis, publisher: StatePublisher,
                          aggregator: WindowAggregator, db: DBWriter) -> None:
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
                    # control 발 WARNING/INFO 이벤트는 event_publisher가 이미 DB에 직접 insert함
                    # — 여기서 calculate() 태우면 telemetry 스키마 없으므로 reported_state가
                    #   전부 None인 snapshot이 만들어져 state:{site}:{device} 키를 오염시킴.
                    if envelope.get("source") == "control":
                        await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                        continue
                    snapshot = calculate(envelope)
                    if snapshot is None:
                        await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                        continue
                    await publisher.publish(snapshot)
                    aggregator.add(snapshot)
                    await client.xack(REDIS_NORMAL_STREAM, CONSUMER_GROUP, msg_id)
                    print(f"[state-processor] {snapshot['device_id']} ({snapshot['resource_type']}) → ems:state")
                except Exception as e:
                    print(f"[state-processor] 처리 실패 id={msg_id} error={e}")


async def _consume_emergency(client: aioredis.Redis, db: DBWriter) -> None:
    """이상 데이터는 즉시 event_log에 저장"""
    try:
        await client.xgroup_create(REDIS_EMERGENCY_STREAM, CONSUMER_GROUP, id="0", mkstream=True)
    except Exception as e:
        if "BUSYGROUP" not in str(e):
            raise

    while True:
        results = await client.xreadgroup(
            groupname=CONSUMER_GROUP,
            consumername=CONSUMER_NAME,
            streams={REDIS_EMERGENCY_STREAM: ">"},
            count=10,
            block=1000,
        )
        if not results:
            continue

        for _, messages in results:
            for msg_id, fields in messages:
                try:
                    envelope = json.loads(fields["data"])
                    # control 발 이벤트는 event_publisher가 이미 DB에 직접 insert함
                    # — 여기서 또 insert하면 중복 저장되므로 xack만 하고 skip
                    if envelope.get("source") == "control":
                        await client.xack(REDIS_EMERGENCY_STREAM, CONSUMER_GROUP, msg_id)
                        continue
                    # control 발 envelope는 device_id 키 사용 — resource_id로 정규화
                    if "resource_id" not in envelope and "device_id" in envelope:
                        envelope["resource_id"] = envelope["device_id"]
                    snapshot = calculate(envelope)
                    if snapshot is None:
                        await client.xack(REDIS_EMERGENCY_STREAM, CONSUMER_GROUP, msg_id)
                        print(f"[state-processor] emergency envelope 무시 (calculate=None): {envelope.get('resource_id') or envelope.get('device_id')}")
                        continue
                    await db.insert_event(
                        snapshot,
                        event_type=envelope.get("event_type", "EVT-E-000"),
                        severity=envelope.get("severity", "EMERGENCY"),
                        message=envelope.get("message", ""),
                    )
                    await client.xack(REDIS_EMERGENCY_STREAM, CONSUMER_GROUP, msg_id)
                    print(f"[state-processor] emergency 즉시 저장: {snapshot['device_id']}")
                except Exception as e:
                    print(f"[state-processor] emergency 처리 실패 id={msg_id} error={e}")


async def _batch_flush(aggregator: WindowAggregator, db: DBWriter) -> None:
    """1초마다 집계 결과를 TimescaleDB에 INSERT"""
    while True:
        await asyncio.sleep(1.0)
        rows = aggregator.flush()
        if rows:
            try:
                await db.insert_sensor_batch(rows)
                print(f"[db-writer] {len(rows)}개 설비 집계 INSERT 완료")
            except Exception as e:
                print(f"[db-writer] INSERT 실패: {e}")


async def run(publisher: StatePublisher) -> None:
    client = aioredis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    await _ensure_group(client, REDIS_NORMAL_STREAM)

    db = DBWriter()
    await db.connect()

    aggregator = WindowAggregator()

    await asyncio.gather(
        _consume_normal(client, publisher, aggregator, db),
        _consume_emergency(client, db),
        _batch_flush(aggregator, db),
    )
