#!/bin/bash
set -e

# ================================================
# PostgreSQL 초기화 스크립트 (멱등)
# - State / AI / Control 3개 DB 논리 분리
# - 서비스별 전용 유저
# - 재실행해도 안전 (bind mount 환경에서 EC2 재시작 시 대비)
# ================================================

# 1. 유저 생성 (존재 시 skip)
#    CREATE USER 는 IF NOT EXISTS 미지원 → DO 블록 + pg_roles 조회로 가드
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${STATE_USER}') THEN
            CREATE USER ${STATE_USER} WITH PASSWORD '${STATE_PASSWORD}';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${AI_USER}') THEN
            CREATE USER ${AI_USER} WITH PASSWORD '${AI_PASSWORD}';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${CONTROL_USER}') THEN
            CREATE USER ${CONTROL_USER} WITH PASSWORD '${CONTROL_PASSWORD}';
        END IF;
    END
    \$\$;
EOSQL

# 2. DB 생성 (존재 시 skip)
#    CREATE DATABASE 는 트랜잭션 밖에서만 가능 → \gexec 로 동적 실행
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${STATE_DB} OWNER ${STATE_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${STATE_DB}')\gexec

    SELECT 'CREATE DATABASE ${AI_DB} OWNER ${AI_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${AI_DB}')\gexec

    SELECT 'CREATE DATABASE ${CONTROL_DB} OWNER ${CONTROL_USER}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${CONTROL_DB}')\gexec

    -- GRANT 는 재실행 멱등
    GRANT ALL PRIVILEGES ON DATABASE ${STATE_DB}   TO ${STATE_USER};
    GRANT ALL PRIVILEGES ON DATABASE ${AI_DB}      TO ${AI_USER};
    GRANT ALL PRIVILEGES ON DATABASE ${CONTROL_DB} TO ${CONTROL_USER};
EOSQL

# 3. PG15 public schema 권한 부여 (각 DB 별 개별 연결 필요, 멱등)
for pair in "${STATE_DB}:${STATE_USER}" "${AI_DB}:${AI_USER}" "${CONTROL_DB}:${CONTROL_USER}"; do
    DB_NAME="${pair%%:*}"
    DB_USER="${pair##*:}"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
        GRANT ALL ON SCHEMA public TO ${DB_USER};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
EOSQL
done

echo "===== init_postgres.sh 완료 (idempotent): state_write / ai / control 3개 DB + 유저 ====="
