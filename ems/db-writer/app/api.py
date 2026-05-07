"""db-writer Flask app.

용도: /health endpoint + 백그라운드 worker 스레드 시작.
실제 데이터 저장 로직은 adapters/stream_consumer.py 의 worker 가 담당.
"""

import asyncio
import threading

from flask import Flask, jsonify
from prometheus_flask_exporter import PrometheusMetrics

from .config import (
    REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
    TIMESCALE_HOST, TIMESCALE_PORT, TIMESCALE_DB, TIMESCALE_USER, TIMESCALE_PASSWORD,
    STATE_DB_HOST, STATE_DB_PORT, STATE_DB_NAME, STATE_DB_USER, STATE_DB_PASSWORD,
)


def create_app() -> Flask:
    app = Flask(__name__)
    PrometheusMetrics(app, group_by="endpoint")

    @app.route("/health")
    def health():
        errors = []
        # Redis 연결 확인
        try:
            import redis as _redis
            r = _redis.Redis(
                host=REDIS_HOST, port=REDIS_PORT,
                password=REDIS_PASSWORD, socket_connect_timeout=2,
            )
            r.ping()
            r.close()
        except Exception as e:
            errors.append(f"redis: {e}")

        # TimescaleDB 연결 확인
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=TIMESCALE_HOST, port=TIMESCALE_PORT, dbname=TIMESCALE_DB,
                user=TIMESCALE_USER, password=TIMESCALE_PASSWORD, connect_timeout=2,
            )
            conn.close()
        except Exception as e:
            errors.append(f"timescale: {e}")

        # PostgreSQL state_write_db 연결 확인
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=STATE_DB_HOST, port=STATE_DB_PORT, dbname=STATE_DB_NAME,
                user=STATE_DB_USER, password=STATE_DB_PASSWORD, connect_timeout=2,
            )
            conn.close()
        except Exception as e:
            errors.append(f"postgres: {e}")

        if errors:
            return jsonify({"status": "degraded", "service": "db-writer", "errors": errors}), 503
        return jsonify({"status": "ok", "service": "db-writer"})

    _start_worker()
    return app


def _start_worker() -> None:
    """백그라운드 스레드에서 stream consumer 실행."""
    from .adapters.stream_consumer import run as run_worker

    thread = threading.Thread(target=asyncio.run, args=(run_worker(),), daemon=True)
    thread.start()
    print("[db-writer] worker 스레드 시작")


app = create_app()
