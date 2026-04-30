"""control 설정.

master .env 매핑:
  - DB는 PostgreSQL `control_db` 사용 (TimescaleDB는 시계열 전용).
    → POSTGRES_*  + CONTROL_*  변수를 우선.
  - REDIS_PASSWORD, MQTT_USER/PASSWORD 추가.
"""

import os

# ── MQTT ───────────────────────────────────────────────────────────────────
MQTT_HOST = os.getenv("MQTT_BROKER_HOST") or os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT") or os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None

# ── Site / 운영 정책 ───────────────────────────────────────────────────────
SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")
CONTROL_INTERVAL_SECONDS = 1.0
TIMEZONE = os.getenv("TIMEZONE", "Asia/Seoul")

# ── DB (PostgreSQL control_db) ────────────────────────────────────────────
# master .env 우선 (POSTGRES_* + CONTROL_*), 옛 변수도 fallback
DB_HOST = os.getenv("POSTGRES_HOST") or os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT") or os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("CONTROL_DB") or os.getenv("DB_NAME", "emsdb")
DB_USER = os.getenv("CONTROL_USER") or os.getenv("DB_USER", "ems")
DB_PASSWORD = os.getenv("CONTROL_PASSWORD") or os.getenv("DB_PASSWORD", "ems1234")
