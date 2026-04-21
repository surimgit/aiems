import asyncio
import threading
from adapters.stream_consumer import run
from adapters.state_publisher import StatePublisher
from api import run_api


async def main():
    publisher = StatePublisher()
    try:
        await run(publisher)
    finally:
        await publisher.close()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, kwargs={"port": 5002}, daemon=True)
    api_thread.start()
    print("[state-processor] Flask API 시작: port 5002")
    asyncio.run(main())
