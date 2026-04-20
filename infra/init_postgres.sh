#!/bin/bash
set -e

# ================================================
# PostgreSQL 초기화 스크립트
# - State / AI / Control 3개 DB 논리 분리
# - 서비스별 전용 유저
# ================================================

# 1. DB 3개 + 유저 3개 생성
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER ${STATE_USER}   WITH PASSWORD '${STATE_PASSWORD}';
    CREATE USER ${AI_USER}      WITH PASSWORD '${AI_PASSWORD}';
    CREATE USER ${CONTROL_USER} WITH PASSWORD '${CONTROL_PASSWORD}';

    CREATE DATABASE ${STATE_DB}   OWNER ${STATE_USER};
    CREATE DATABASE ${AI_DB}      OWNER ${AI_USER};
    CREATE DATABASE ${CONTROL_DB} OWNER ${CONTROL_USER};

    GRANT ALL PRIVILEGES ON DATABASE ${STATE_DB}   TO ${STATE_USER};
    GRANT ALL PRIVILEGES ON DATABASE ${AI_DB}      TO ${AI_USER};
    GRANT ALL PRIVILEGES ON DATABASE ${CONTROL_DB} TO ${CONTROL_USER};
EOSQL

# 2. PG15 public schema 권한 부여 (각 DB별 개별 연결 필요)
for pair in "${STATE_DB}:${STATE_USER}" "${AI_DB}:${AI_USER}" "${CONTROL_DB}:${CONTROL_USER}"; do
    DB_NAME="${pair%%:*}"
    DB_USER="${pair##*:}"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
        GRANT ALL ON SCHEMA public TO ${DB_USER};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
EOSQL
done

echo "===== init_postgres.sh 완료: state_write / ai / control 3개 DB + 유저 ====="
