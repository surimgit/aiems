import asyncio
from adapters.stream_consumer import run
from adapters.state_publisher import StatePublisher


async def main():
    publisher = StatePublisher()
    try:
        await run(publisher)
    finally:
        await publisher.close()


if __name__ == "__main__":
    asyncio.run(main())
