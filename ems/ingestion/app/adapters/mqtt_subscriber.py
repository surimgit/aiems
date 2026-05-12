import asyncio
import json
import aiomqtt
import redis.asyncio as aioredis
from ..config import (
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
    SITE_ID, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
)
from ..domain.normalizer import normalize
from ..domain.classifier import classify
from .redis_publisher import RedisPublisher
from .telemetry_coalescer import TelemetryCoalescer

_HEARTBEAT_TTL_SEC = 30  # 시뮬레이터 10초 주기 × 3회 미수신 시 만료
_HEARTBEAT_PREFIX = "ems:heartbeat:"

TOPICS = [
    f"{SITE_ID}/+/+/telemetry",
    f"{SITE_ID}/+/+/event",
    f"{SITE_ID}/+/+/emergency",
    f"{SITE_ID}/+/+/ack",
    f"{SITE_ID}/heartbeat",
]

_RECONNECT_DELAY_SEC = 5


async def run(publisher: RedisPublisher) -> None:
    redis = aioredis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASSWORD, decode_responses=True,
    )
    coalescer = TelemetryCoalescer(publisher)
    flush_task = asyncio.create_task(coalescer.run())
    try:
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=MQTT_HOST, port=MQTT_PORT,
                    username=MQTT_USER, password=MQTT_PASSWORD,
                ) as client:
                    for topic in TOPICS:
                        await client.subscribe(topic)
                    print(f"[ingestion] MQTT 구독 시작: {TOPICS}")

                    async for message in client.messages:
                        topic = str(message.topic)
                        try:
                            parts = topic.split("/")

                            if len(parts) == 2 and parts[1] == "heartbeat":
                                try:
                                    hb = json.loads(message.payload)
                                    device_id = hb.get("device_id")
                                    if device_id:
                                        key = f"{_HEARTBEAT_PREFIX}{SITE_ID}:{device_id}"
                                        await redis.setex(key, _HEARTBEAT_TTL_SEC, hb.get("timestamp", ""))
                                        print(f"[ingestion] heartbeat: {device_id}")
                                except Exception as e:
                                    print(f"[ingestion] heartbeat 파싱 실패: {e}")
                                continue

                            message_type = parts[3]
                            if message_type == "ack":
                                continue  # ACK는 control이 직접 처리, state stream 불필요
                            envelope = normalize(topic, message.payload)
                            stream = classify(message_type)

                            if message_type == "telemetry":
                                await coalescer.add(stream, envelope)
                            else:
                                await publisher.publish(stream, envelope)
                                print(f"[ingestion] {topic} → {stream}")
                        except Exception as e:
                            print(f"[ingestion] 처리 실패 topic={topic} error={e}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ingestion] MQTT 연결 끊김: {e} — {_RECONNECT_DELAY_SEC}s 후 재연결")
                await asyncio.sleep(_RECONNECT_DELAY_SEC)
    finally:
        flush_task.cancel()
        try:
            await flush_task
        except asyncio.CancelledError:
            pass
        await coalescer.flush()
        await redis.aclose()
