import asyncio
from adapters.mqtt_subscriber import run
from adapters.redis_publisher import RedisPublisher


async def main():
    publisher = RedisPublisher()
    try:
        await run(publisher)
    finally:
        await publisher.close()


if __name__ == "__main__":
    asyncio.run(main())
