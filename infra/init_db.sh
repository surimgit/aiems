#!/bin/bash
set -e

# ================================================
# SSAFY S305 - DB 초기화 스크립트
# docker-entrypoint-initdb.d에서 자동 실행됨
# PostgreSQL 15+ public schema 권한 이슈 반영
# ================================================

# 1. DB 4개 생성
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE monitoring_db;
    CREATE DATABASE ingestion_db;
    CREATE DATABASE forecast_db;
    CREATE DATABASE report_db;
EOSQL

# 2. 서비스별 전용 계정 생성
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE USER monitoring_user WITH PASSWORD 'monitoring_pw';
    CREATE USER ingestion_user WITH PASSWORD 'ingestion_pw';
    CREATE USER forecast_user WITH PASSWORD 'forecast_pw';
    CREATE USER report_user WITH PASSWORD 'report_pw';
EOSQL

# 3. DB 단위 권한 부여
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    GRANT ALL PRIVILEGES ON DATABASE monitoring_db TO monitoring_user;
    GRANT ALL PRIVILEGES ON DATABASE ingestion_db TO ingestion_user;
    GRANT ALL PRIVILEGES ON DATABASE forecast_db TO forecast_user;
    GRANT ALL PRIVILEGES ON DATABASE report_db TO report_user;
EOSQL

# 4. PG15 public schema 권한 부여 (필수!)
# 각 DB에 개별 연결하여 schema 권한 부여
for pair in "monitoring_db:monitoring_user" "ingestion_db:ingestion_user" "forecast_db:forecast_user" "report_db:report_user"; do
    DB_NAME="${pair%%:*}"
    DB_USER="${pair##*:}"
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_NAME" <<-EOSQL
        GRANT ALL ON SCHEMA public TO ${DB_USER};
        GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO ${DB_USER};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
EOSQL
done

echo "===== init_db.sh 완료: DB 4개 + 계정 4개 + PG15 schema 권한 설정 완료 ====="
