"""ingestion 설정.

환경변수 우선순위:
  1) .env (Jenkins Managed File 또는 docker compose env_file)
  2) docker-compose 의 environment: 블록
  3) 코드 default (로컬 개발용)

master .env 명명 규약을 따른다:
  - MQTT_BROKER_HOST / MQTT_BROKER_PORT (우리 옛 코드는 MQTT_HOST 사용 → 통합)
  - REDIS_PASSWORD / MQTT_USER / MQTT_PASSWORD 추가
"""

import os

# ── MQTT ───────────────────────────────────────────────────────────────────
# master .env 우선, 옛 변수명도 fallback 으로 인정 (로컬 호환)
MQTT_HOST = os.getenv("MQTT_BROKER_HOST") or os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT") or os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")            # 인증 활성화 시 필수
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")    # 인증 활성화 시 필수

# ── Redis ──────────────────────────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None  # 빈 문자열도 None 처리

# ── Site / Streams ─────────────────────────────────────────────────────────
SITE_ID = os.getenv("SITE_ID", "PLANT-ALPHA")
REDIS_NORMAL_STREAM = "mg:sensor:data"
REDIS_EMERGENCY_STREAM = "mg:emergency:event"
STREAM_MAXLEN = int(os.getenv("STREAM_MAXLEN", 10000))
