import asyncio
import threading
from adapters.mqtt_subscriber import run
from adapters.redis_publisher import RedisPublisher
from api import run_api


async def main():
    publisher = RedisPublisher()
    try:
        await run(publisher)
    finally:
        await publisher.close()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, kwargs={"port": 5000}, daemon=True)
    api_thread.start()
    print("[ingestion] Flask API 시작: port 5000")
    asyncio.run(main())
