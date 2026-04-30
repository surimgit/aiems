"""Redis Stream consumer — 모든 저장 트래픽의 단일 진입점.

구독 stream:
  - mg:state:result      → sensor_data 1초 batch + device_meta upsert
  - mg:emergency:event   → event_log 즉시 INSERT
  - mg:db:write          → kind 필드로 dispatch
                              kind="command" → control_history INSERT/UPDATE
                              kind="comms"   → comms_health_log INSERT
"""

import asyncio
import json

import redis.asyncio as aioredis

from ..config import (
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
    STREAM_STATE_RESULT, STREAM_EMERGENCY_EVENT, STREAM_DB_WRITE,
    CONSUMER_GROUP, CONSUMER_NAME,
    FLUSH_INTERVAL_SEC,
)
from ..domain.aggregator import WindowAggregator
from .timescale_writer import TimescaleWriter
from .postgres_writer import PostgresWriter


async def _ensure_group(client: aioredis.Redis, stream: str) -> None:
    """consumer group이 없으면 생성. init_streams.py가 이미 만들었으면 BUSYGROUP."""
    try:
        await client.xgroup_create(stream, CONSUMER_GROUP, id="0", mkstream=True)
        print(f"[db-writer] consumer group 생성: {CONSUMER_GROUP} / {stream}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            pass
        else:
            raise


# ── 메시지 처리 ───────────────────────────────────────────────────────────

async def _handle_state_result(
    client: aioredis.Redis,
    msg_id: str,
    fields: dict,
    aggregator: WindowAggregator,
    pg: PostgresWriter,
) -> None:
    """mg:state:result — state-processor가 계산한 device 상태 스냅샷."""
    try:
        snapshot = json.loads(fields["data"])
        # 1초 batch 집계 버퍼에 추가 (flush 시 sensor_data INSERT)
        aggregator.add(snapshot)
        # device_meta upsert (last_seen_at 갱신)
        await pg.upsert_device_seen(snapshot)
        await client.xack(STREAM_STATE_RESULT, CONSUMER_GROUP, msg_id)
    except Exception as e:
        print(f"[db-writer] state_result 처리 실패 id={msg_id} error={e}")


async def _handle_emergency(
    client: aioredis.Redis,
    msg_id: str,
    fields: dict,
    ts: TimescaleWriter,
) -> None:
    """mg:emergency:event — 긴급 이벤트 즉시 event_log INSERT."""
    try:
        envelope = json.loads(fields["data"])
        await ts.insert_event(envelope)
        await client.xack(STREAM_EMERGENCY_EVENT, CONSUMER_GROUP, msg_id)
    except Exception as e:
        print(f"[db-writer] emergency 처리 실패 id={msg_id} error={e}")


async def _handle_db_write(
    client: aioredis.Redis,
    msg_id: str,
    fields: dict,
    ts: TimescaleWriter,
    pg: PostgresWriter,
) -> None:
    """mg:db:write — kind 필드로 분기.
       kind=command : control_history (INSERT or UPDATE ack)
       kind=event   : event_log (WARNING/INFO 등 비-CRITICAL 이벤트)
       kind=comms   : comms_health_log
    """
    try:
        envelope = json.loads(fields["data"])
        kind = envelope.get("kind")
        if kind == "command":
            # ack 갱신용 행이면 UPDATE, 신규 발행이면 INSERT
            if envelope.get("update_ack"):
                await ts.update_command_ack(
                    envelope["command_id"],
                    envelope.get("ack_status", "accepted"),
                    envelope.get("verified"),
                )
            else:
                await ts.insert_command(envelope)
        elif kind == "event":
            # CRITICAL 은 mg:emergency:event 로 따로 들어옴. 여기는 WARNING/INFO.
            await ts.insert_event(envelope)
        elif kind == "comms":
            await pg.insert_comms_event(envelope)
        else:
            print(f"[db-writer] db:write 알 수 없는 kind={kind}, skip")
        await client.xack(STREAM_DB_WRITE, CONSUMER_GROUP, msg_id)
    except Exception as e:
        print(f"[db-writer] db:write 처리 실패 id={msg_id} error={e}")


# ── 메인 루프 ────────────────────────────────────────────────────────────

async def _consume_loop(
    client: aioredis.Redis,
    aggregator: WindowAggregator,
    ts: TimescaleWriter,
    pg: PostgresWriter,
) -> None:
    """3개 stream을 동시에 읽어 dispatch."""
    streams = {
        STREAM_STATE_RESULT: ">",
        STREAM_EMERGENCY_EVENT: ">",
        STREAM_DB_WRITE: ">",
    }
    while True:
        try:
            results = await client.xreadgroup(
                groupname=CONSUMER_GROUP,
                consumername=CONSUMER_NAME,
                streams=streams,
                count=50,
                block=1000,
            )
            if not results:
                continue
            for stream, messages in results:
                for msg_id, fields in messages:
                    if stream == STREAM_STATE_RESULT:
                        await _handle_state_result(client, msg_id, fields, aggregator, pg)
                    elif stream == STREAM_EMERGENCY_EVENT:
                        await _handle_emergency(client, msg_id, fields, ts)
                    elif stream == STREAM_DB_WRITE:
                        await _handle_db_write(client, msg_id, fields, ts, pg)
        except Exception as e:
            print(f"[db-writer] consume loop 오류: {e}")
            await asyncio.sleep(1.0)


async def _batch_flush(aggregator: WindowAggregator, ts: TimescaleWriter) -> None:
    """1초마다 sensor_data 집계 결과를 TimescaleDB에 INSERT."""
    while True:
        await asyncio.sleep(FLUSH_INTERVAL_SEC)
        rows = aggregator.flush()
        if not rows:
            continue
        try:
            await ts.insert_sensor_batch(rows)
            print(f"[db-writer] sensor_data {len(rows)} rows INSERT")
        except Exception as e:
            print(f"[db-writer] sensor_data flush 실패: {e}")


async def run() -> None:
    """db-writer 메인 진입점. 모든 자원 초기화 + 루프 동시 실행."""
    client = aioredis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASSWORD, decode_responses=True,
    )
    ts = TimescaleWriter()
    pg = PostgresWriter()
    await ts.connect()
    await pg.connect()

    # init_streams.py가 이미 group을 만들었지만 safety net으로 ensure
    await _ensure_group(client, STREAM_STATE_RESULT)
    await _ensure_group(client, STREAM_EMERGENCY_EVENT)
    await _ensure_group(client, STREAM_DB_WRITE)

    aggregator = WindowAggregator()

    print("[db-writer] consumer 시작")
    try:
        await asyncio.gather(
            _consume_loop(client, aggregator, ts, pg),
            _batch_flush(aggregator, ts),
        )
    finally:
        await ts.close()
        await pg.close()
        await client.aclose()
