#!/bin/bash
set -e

# ================================================
# TimescaleDB 초기화 스크립트 (멱등)
# - 시계열 데이터 전용 (DB Writer 서비스가 사용)
# - 단일 DB + 단일 유저
# - 재실행해도 안전 (bind mount 환경에서 EC2 재시작 시 대비)
# ================================================

# 1. 유저 생성 (존재 시 skip)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${TIMESCALE_USER}') THEN
            CREATE USER ${TIMESCALE_USER} WITH PASSWORD '${TIMESCALE_PASSWORD}';
        END IF;
    END
    \$\$;
EOSQL

# 2. DB 생성 (존재 시 skip) + 권한 부여 (멱등)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${TIMESCALE_DB} OWNER ${TIMESCALE_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${TIMESCALE_DB}')\gexec

    GRANT ALL PRIVILEGES ON DATABASE ${TIMESCALE_DB} TO ${TIMESCALE_USER};
EOSQL

# 3. public schema 권한 + TimescaleDB 확장 설치 (멱등)
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${TIMESCALE_DB}" <<-EOSQL
    GRANT ALL ON SCHEMA public TO ${TIMESCALE_USER};
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${TIMESCALE_USER};
    CREATE EXTENSION IF NOT EXISTS timescaledb;
EOSQL

echo "===== init_timescale.sh 완료 (idempotent): ${TIMESCALE_DB} + ${TIMESCALE_USER} + TimescaleDB 확장 ====="
