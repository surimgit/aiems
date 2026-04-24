import asyncio
import threading

from flask import Flask, jsonify
from config import REDIS_HOST, REDIS_PORT


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/health")
    def health():
        errors = []
        try:
            import redis as _redis
            r = _redis.Redis(host=REDIS_HOST, port=REDIS_PORT, socket_connect_timeout=2)
            r.ping()
            r.close()
        except Exception as e:
            errors.append(f"redis: {e}")
        if errors:
            return jsonify({"status": "degraded", "errors": errors}), 503
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
