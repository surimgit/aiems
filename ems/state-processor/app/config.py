"""state-processor 설정.

master .env 매핑:
  - DB는 TimescaleDB(시계열) 사용. master .env 의 TIMESCALE_* 변수를 우선 사용.
  - REDIS_PASSWORD 추가.
"""

import os

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

# ── Site / Streams ─────────────────────────────────────────────────────────
SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")
REDIS_NORMAL_STREAM = "mg:sensor:data"
REDIS_EMERGENCY_STREAM = "mg:emergency:event"
REDIS_STATE_STREAM = "mg:state:result"

# 인프라 init_streams.py가 미리 만들어둔 group 이름과 일치시킴
CONSUMER_GROUP = "state-group"
CONSUMER_NAME = "state-processor-1"

# ── DB (TimescaleDB) ──────────────────────────────────────────────────────
# 시계열 (sensor_data / event_log / control_history) 조회용.
DB_HOST = os.getenv("TIMESCALE_HOST") or os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("TIMESCALE_PORT") or os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("TIMESCALE_DB") or os.getenv("DB_NAME", "emsdb")
DB_USER = os.getenv("TIMESCALE_USER") or os.getenv("DB_USER", "ems")
DB_PASSWORD = os.getenv("TIMESCALE_PASSWORD") or os.getenv("DB_PASSWORD", "ems1234")

# ── Control DB (PostgreSQL) ───────────────────────────────────────────────
# 운영 데이터 (topology_*, control_policy 등) 조회용.
# state-processor 가 토폴로지 응답을 만들기 위해 read-only 로 접근.
CONTROL_DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
CONTROL_DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))
CONTROL_DB_NAME = os.getenv("CONTROL_DB", "control_db")
CONTROL_DB_USER = os.getenv("CONTROL_USER", "control_user")
CONTROL_DB_PASSWORD = os.getenv("CONTROL_PASSWORD", "")
