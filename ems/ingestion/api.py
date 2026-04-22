import asyncio
import threading

from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    _start_worker()
    return app


def _start_worker() -> None:
    from adapters.mqtt_subscriber import run
    from adapters.redis_publisher import RedisPublisher

    async def _run():
        publisher = RedisPublisher()
        try:
            await run(publisher)
        finally:
            await publisher.close()

    thread = threading.Thread(target=asyncio.run, args=(_run(),), daemon=True)
    thread.start()
    print("[ingestion] MQTT worker 시작")


app = create_app()
