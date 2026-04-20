import asyncio
import aiomqtt
from config import MQTT_HOST, MQTT_PORT, SITE_ID
from domain.normalizer import normalize
from domain.classifier import classify
from adapters.redis_publisher import RedisPublisher


TOPICS = [
    f"{SITE_ID}/+/+/telemetry",
    f"{SITE_ID}/+/+/event",
    f"{SITE_ID}/+/+/emergency",
    f"{SITE_ID}/+/+/ack",
]


async def run(publisher: RedisPublisher) -> None:
    async with aiomqtt.Client(hostname=MQTT_HOST, port=MQTT_PORT) as client:
        for topic in TOPICS:
            await client.subscribe(topic)
        print(f"[ingestion] MQTT 구독 시작: {TOPICS}")

        async for message in client.messages:
            topic = str(message.topic)
            try:
                parts = topic.split("/")
                message_type = parts[3]

                envelope = normalize(topic, message.payload)
                stream = classify(message_type)

                await publisher.publish(stream, envelope)
                print(f"[ingestion] {topic} → {stream}")
            except Exception as e:
                print(f"[ingestion] 처리 실패 topic={topic} error={e}")
