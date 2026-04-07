"""
Redis Streams Consumer Group 초기화 스크립트
- AWS Phase 2 Step 6에서 1회 실행
- 로컬에서는 docker compose up 후 수동 실행
- 레이스 컨디션 원천 차단
"""
import os
import redis

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    decode_responses=True,
)

GROUPS = [
    ("mg:sensor:data", "monitoring-group"),
    ("mg:sensor:data", "forecast-group"),
    ("mg:sensor:alert", "monitoring-group"),
    ("mg:control:cmd", "ingestion-group"),
    ("mg:forecast:result", "monitoring-group"),
    ("mg:forecast:result", "report-group"),
    ("mg:report:trigger", "report-group"),
]

for stream, group in GROUPS:
    try:
        r.xgroup_create(stream, group, id='0', mkstream=True)
        print(f"[OK] created: {stream} / {group}")
    except redis.exceptions.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"[SKIP] exists: {stream} / {group}")
        else:
            raise
