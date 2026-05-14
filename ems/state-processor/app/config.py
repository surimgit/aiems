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

# dev/app state-processor가 같은 Redis stream을 동시에 볼 수 있으므로
# 배포 환경별로 consumer group/name을 분리할 수 있게 둔다.
CONSUMER_GROUP = os.getenv("STATE_CONSUMER_GROUP", "state-group")
CONSUMER_NAME = os.getenv("STATE_CONSUMER_NAME", "state-processor-1")

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

# ── Simulator Topology API (legacy/dev fallback) ───────────────────────────
# LOCAL_SIM_TOPOLOGY_MQTT_ENABLED=false 인 개발 환경에서만 사용한다.
# 서버 배포 기준 topology 구조 수신은 ingestion 의 MQTT subscriber 가 담당하고,
# state-processor 는 Redis cache 만 조회한다.
SIMULATOR_TOPOLOGY_URL = os.getenv("SIMULATOR_TOPOLOGY_URL", "http://host.docker.internal:8081")

# ── Local simulator topology over MQTT ─────────────────────────────────────
# true 이면 control_db 기본 topology 와 simulator HTTP fallback 을 쓰지 않고,
# simulator-manager 가 MQTT 로 발행한 snapshot cache 를 프론트 조회 API의 정본으로 사용한다.
LOCAL_SIM_TOPOLOGY_MQTT_ENABLED = os.getenv(
    "LOCAL_SIM_TOPOLOGY_MQTT_ENABLED",
    "true",
).lower() in ("1", "true", "yes", "on")

# ── Socket.IO ──────────────────────────────────────────────────────────────
# 로컬 프론트/게이트웨이 개발 편의를 위해 기본은 전체 허용.
# 운영에서 별도 도메인으로 제한하려면 쉼표 구분 문자열로 지정한다.
_socketio_origins = os.getenv("SOCKETIO_CORS_ALLOWED_ORIGINS", "*")
SOCKETIO_CORS_ALLOWED_ORIGINS = (
    [origin.strip() for origin in _socketio_origins.split(",") if origin.strip()]
    if _socketio_origins != "*"
    else "*"
)
