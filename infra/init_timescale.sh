#!/bin/bash
set -e

# ================================================
# TimescaleDB 초기화 스크립트
# - 시계열 데이터 전용 (DB Writer 서비스가 사용)
# - 단일 DB + 단일 유저
# ================================================

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER ${TIMESCALE_USER} WITH PASSWORD '${TIMESCALE_PASSWORD}';
    CREATE DATABASE ${TIMESCALE_DB} OWNER ${TIMESCALE_USER};
    GRANT ALL PRIVILEGES ON DATABASE ${TIMESCALE_DB} TO ${TIMESCALE_USER};
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${TIMESCALE_DB}" <<-EOSQL
    GRANT ALL ON SCHEMA public TO ${TIMESCALE_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${TIMESCALE_USER};
    CREATE EXTENSION IF NOT EXISTS timescaledb;
EOSQL

echo "===== init_timescale.sh 완료: ${TIMESCALE_DB} + ${TIMESCALE_USER} + TimescaleDB 확장 ====="
