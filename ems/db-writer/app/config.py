"""db-writer 설정.

DB Writer는 모든 저장의 단일 게이트(문서 04-services/db-writer.md)이므로
TimescaleDB + PostgreSQL 두 DB 모두에 연결한다.

  - TimescaleDB: sensor_data, event_log, control_history (시계열)
  - PostgreSQL.state_write_db: device_meta, comms_health_log (state_meta)

Redis stream 이름은 인프라 명명규약(`mg:*`) 사용.
"""

import os

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

# ── Site ───────────────────────────────────────────────────────────────────
SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")

# ── Redis Streams (인프라 명명규약 mg:*) ──────────────────────────────────
STREAM_STATE_RESULT = "mg:state:result"        # state-processor → sensor_data 집계
STREAM_EMERGENCY_EVENT = "mg:emergency:event"  # 긴급 이벤트 → event_log
STREAM_DB_WRITE = "mg:db:write"                # 명시적 저장 요청 (control_history 등)

CONSUMER_GROUP = "db-writer-group"             # init_streams.py와 일치
CONSUMER_NAME = "db-writer-1"

# 1초 batch flush 주기 (sensor_data 집계용)
FLUSH_INTERVAL_SEC = 1.0

# ── TimescaleDB (sensor_data / event_log / control_history) ───────────────
TIMESCALE_HOST = os.getenv("TIMESCALE_HOST", "timescaledb")
TIMESCALE_PORT = int(os.getenv("TIMESCALE_PORT", 5432))
TIMESCALE_DB = os.getenv("TIMESCALE_DB", "timescale_db")
TIMESCALE_USER = os.getenv("TIMESCALE_USER", "timescale_user")
TIMESCALE_PASSWORD = os.getenv("TIMESCALE_PASSWORD", "")

# ── PostgreSQL.state_write_db (device_meta / comms_health_log) ────────────
STATE_DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
STATE_DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
STATE_DB_NAME = os.getenv("STATE_DB", "state_write_db")
STATE_DB_USER = os.getenv("STATE_USER", "state_user")
STATE_DB_PASSWORD = os.getenv("STATE_PASSWORD", "")
