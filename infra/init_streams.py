"""
Redis Streams Consumer Group 초기화 스크립트
- docker-compose 기동 시 stream-init oneshot 컨테이너가 자동 실행
- 모든 서비스가 Redis 구독 전에 그룹이 반드시 존재하도록 보장
- Normal + Emergency 2개 이벤트 버스 모두 커버
"""
import logging
import os
import sys
import time

import redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("stream-init")

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
MAX_RETRIES = int(os.getenv("STREAM_INIT_MAX_RETRIES", 30))
RETRY_INTERVAL = float(os.getenv("STREAM_INIT_RETRY_INTERVAL", 2.0))

# (stream, consumer_group)
GROUPS = [
    # --- Normal Event Bus ---
    ("mg:sensor:data", "state-group"),
    ("mg:sensor:data", "ai-group"),
    ("mg:sensor:alert", "state-group"),
    ("mg:control:cmd", "ingestion-group"),
    ("mg:state:result", "db-writer-group"),
    ("mg:ai:result", "control-group"),
    ("mg:ai:result", "db-writer-group"),
    ("mg:db:write", "db-writer-group"),
    # --- Emergency Event Bus ---
    ("mg:emergency:event", "state-group"),
    ("mg:emergency:event", "control-group"),
    ("mg:emergency:event", "db-writer-group"),
]


def connect_with_retry() -> redis.Redis:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            client.ping()
            log.info("connected to redis %s:%s (attempt %d)", REDIS_HOST, REDIS_PORT, attempt)
            return client
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            last_err = e
            log.warning("redis not ready (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
            time.sleep(RETRY_INTERVAL)
    log.error("redis unreachable after %d attempts: %s", MAX_RETRIES, last_err)
    sys.exit(1)


def ensure_group(client: redis.Redis, stream: str, group: str) -> None:
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
        log.info("created: %s / %s", stream, group)
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            log.info("exists : %s / %s", stream, group)
        else:
            raise


def main() -> None:
    client = connect_with_retry()
    for stream, group in GROUPS:
        ensure_group(client, stream, group)
    log.info("all %d consumer groups ready", len(GROUPS))


if __name__ == "__main__":
    main()
