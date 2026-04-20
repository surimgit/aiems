#!/usr/bin/env bash
# .env 파일에 필수 변수가 모두 채워졌는지 검증
# - 사용: ./infra/check_env.sh [경로]  (기본 .env)
# - 누락 시 exit 1, 모두 OK 면 exit 0

set -u

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo "[check_env] ERROR: $ENV_FILE 파일이 없습니다." >&2
    exit 1
fi

REQUIRED=(
    TIMESCALE_PASSWORD
    TIMESCALE_ROOT_PASSWORD
    POSTGRES_ROOT_PASSWORD
    STATE_PASSWORD
    AI_PASSWORD
    CONTROL_PASSWORD
    REDIS_PASSWORD
    MQTT_USER
    MQTT_PASSWORD
    API_SECRET_KEY
    JWT_SECRET
)

MISSING=()
for key in "${REQUIRED[@]}"; do
    value=$(grep -E "^${key}=" "$ENV_FILE" | head -n1 | cut -d= -f2- | sed 's/#.*$//' | xargs || true)
    if [ -z "$value" ]; then
        MISSING+=("$key")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "[check_env] ERROR: 다음 필수 환경변수가 비어있습니다:" >&2
    for key in "${MISSING[@]}"; do
        echo "  - $key" >&2
    done
    exit 1
fi

echo "[check_env] OK: 필수 환경변수 ${#REQUIRED[@]}개 모두 설정됨"
