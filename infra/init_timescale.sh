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

# ============================================================
# 4. sensor_data 스키마 + hypertable + 집계 뷰 + 정책
#    - INSERT 주체: db-writer (Redis stream 에서 1초 배치 집계 후 INSERT)
#    - SELECT 주체: state-processor (외부 connection, 차트/대시보드용)
#    멱등: CREATE TABLE IF NOT EXISTS / if_not_exists => TRUE
# ============================================================
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${TIMESCALE_DB}" <<-EOSQL
    -- ── sensor_data 테이블 ────────────────────────────────────
    CREATE TABLE IF NOT EXISTS sensor_data (
        time            TIMESTAMPTZ     NOT NULL,
        site_id         VARCHAR(64)     NOT NULL,
        device_id       VARCHAR(64)     NOT NULL,
        resource_type   VARCHAR(32)     NOT NULL,  -- SOLAR / ESS / LOAD / DIESEL
        p_avg           FLOAT,
        p_max           FLOAT,
        p_min           FLOAT,
        q_avg           FLOAT,
        v_avg           FLOAT,
        i_avg           FLOAT,
        f_avg           FLOAT,
        pf_avg          FLOAT,
        soc             FLOAT,
        kwh             FLOAT,
        sample_count    INT             DEFAULT 1
    );

    -- hypertable 변환 (멱등)
    SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

    CREATE INDEX IF NOT EXISTS idx_sensor_data_device ON sensor_data (device_id, time DESC);
    CREATE INDEX IF NOT EXISTS idx_sensor_data_site   ON sensor_data (site_id, time DESC);

    -- ── 1분 단위 집계 뷰 (continuous aggregate) ───────────────
    CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_1m
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 minute', time)   AS bucket,
        site_id,
        device_id,
        resource_type,
        AVG(p_avg)                      AS p_avg,
        MAX(p_max)                      AS p_max,
        MIN(p_min)                      AS p_min,
        AVG(q_avg)                      AS q_avg,
        AVG(v_avg)                      AS v_avg,
        AVG(f_avg)                      AS f_avg,
        AVG(pf_avg)                     AS pf_avg,
        AVG(soc)                        AS soc_avg,
        SUM(sample_count)               AS sample_count
    FROM sensor_data
    GROUP BY bucket, site_id, device_id, resource_type
    WITH NO DATA;

    SELECT add_continuous_aggregate_policy('sensor_data_1m',
        start_offset => INTERVAL '10 minutes',
        end_offset   => INTERVAL '1 minute',
        schedule_interval => INTERVAL '1 minute',
        if_not_exists => TRUE
    );

    -- ── 1시간 단위 집계 뷰 ────────────────────────────────────
    CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_1h
    WITH (timescaledb.continuous) AS
    SELECT
        time_bucket('1 hour', time)     AS bucket,
        site_id,
        device_id,
        resource_type,
        AVG(p_avg)                      AS p_avg,
        MAX(p_max)                      AS p_max,
        MIN(p_min)                      AS p_min,
        AVG(q_avg)                      AS q_avg,
        AVG(v_avg)                      AS v_avg,
        AVG(f_avg)                      AS f_avg,
        AVG(pf_avg)                     AS pf_avg,
        AVG(soc)                        AS soc_avg,
        SUM(sample_count)               AS sample_count
    FROM sensor_data
    GROUP BY bucket, site_id, device_id, resource_type
    WITH NO DATA;

    -- start_offset(3h) - end_offset(1h) = 2h 윈도우 ≥ 2*bucket(1h) 충족
    SELECT add_continuous_aggregate_policy('sensor_data_1h',
        start_offset => INTERVAL '3 hours',
        end_offset   => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour',
        if_not_exists => TRUE
    );

    -- ── 압축 정책 (7일 이상 데이터 압축) ──────────────────────
    ALTER TABLE sensor_data SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'device_id, resource_type'
    );

    SELECT add_compression_policy('sensor_data',
        compress_after => INTERVAL '7 days',
        if_not_exists => TRUE
    );

    -- ── 보존 정책 (90일 이후 자동 삭제) ───────────────────────
    SELECT add_retention_policy('sensor_data',
        drop_after => INTERVAL '90 days',
        if_not_exists => TRUE
    );

    -- ============================================================
    -- event_log (이상/알람 이벤트 — 문서 §3 'event = TimescaleDB')
    -- INSERT: DB Writer (단일 게이트, stream consumer)
    -- SELECT: state-processor 알람 조회 API
    -- UPDATE: 알람 acknowledge (압축 chunk 는 UPDATE 불가 → A안: 30d 이내만 가능)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS event_log (
        time            TIMESTAMPTZ     NOT NULL,
        site_id         VARCHAR(64)     NOT NULL,
        device_id       VARCHAR(64)     NOT NULL,
        resource_type   VARCHAR(32)     NOT NULL,
        event_type      VARCHAR(64)     NOT NULL,   -- EVT-N-001, EVT-E-001 등
        severity        VARCHAR(16)     NOT NULL,   -- INFO/WARNING/CRITICAL/EMERGENCY
        message         TEXT,
        payload         JSONB,
        alarm_id        UUID            DEFAULT gen_random_uuid(),
        acknowledged    BOOLEAN         DEFAULT false,
        acked_at        TIMESTAMPTZ     DEFAULT NULL,
        acked_by        VARCHAR(64)     DEFAULT NULL
    );

    SELECT create_hypertable('event_log', 'time', if_not_exists => TRUE);

    CREATE INDEX IF NOT EXISTS idx_event_log_device   ON event_log (device_id, time DESC);
    CREATE INDEX IF NOT EXISTS idx_event_log_severity ON event_log (severity, time DESC);
    CREATE INDEX IF NOT EXISTS idx_event_log_alarm_id ON event_log (alarm_id);

    -- 압축 정책 (30일 이상): 압축 후 UPDATE 불가 — 알람 ack 는 30d 이내에만
    ALTER TABLE event_log SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'device_id, severity'
    );
    SELECT add_compression_policy('event_log',
        compress_after => INTERVAL '30 days',
        if_not_exists => TRUE
    );

    -- 보존 정책 (90일 이후 자동 삭제)
    SELECT add_retention_policy('event_log',
        drop_after => INTERVAL '90 days',
        if_not_exists => TRUE
    );

    -- ============================================================
    -- control_history (제어 명령 이력 — 문서 §3 'command_result = TimescaleDB')
    -- INSERT: DB Writer (단일 게이트, stream consumer)
    -- SELECT: state-processor 명령 조회 API + control 자체 폐루프 검증 (외부 connection)
    -- ============================================================
    CREATE TABLE IF NOT EXISTS control_history (
        time            TIMESTAMPTZ     NOT NULL,
        command_id      UUID            NOT NULL,
        site_id         VARCHAR(64)     NOT NULL,
        device_id       VARCHAR(64)     NOT NULL,
        resource_type   VARCHAR(32)     NOT NULL,
        command_type    VARCHAR(64)     NOT NULL,
        payload         JSONB           NOT NULL,
        reason          TEXT,
        issued_by       VARCHAR(32)     NOT NULL DEFAULT 'rule',  -- rule/operator/ai
        ack_status      VARCHAR(16)     DEFAULT 'pending',         -- pending/accepted/rejected/timeout
        ack_time        TIMESTAMPTZ,
        verified        BOOLEAN         DEFAULT NULL               -- 폐루프 검증 결과
    );

    SELECT create_hypertable('control_history', 'time', if_not_exists => TRUE);

    CREATE INDEX IF NOT EXISTS idx_control_history_device     ON control_history (device_id, time DESC);
    CREATE INDEX IF NOT EXISTS idx_control_history_command_id ON control_history (command_id);

    -- 압축 정책 (30일 이상)
    ALTER TABLE control_history SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'device_id, resource_type'
    );
    SELECT add_compression_policy('control_history',
        compress_after => INTERVAL '30 days',
        if_not_exists => TRUE
    );

    -- 보존 정책 (180일 이후 자동 삭제) — 감사 추적용으로 sensor_data 보다 길게
    SELECT add_retention_policy('control_history',
        drop_after => INTERVAL '180 days',
        if_not_exists => TRUE
    );
EOSQL

echo "===== init_timescale.sh 완료 ====="
echo "  - timescale_db hypertable 3종 + 압축/보존 정책:"
echo "    · sensor_data       (1m/1h 집계 뷰 + 7d 압축 + 90d 보존)"
echo "    · event_log         (30d 압축 + 90d 보존)"
echo "    · control_history   (30d 압축 + 180d 보존)"
