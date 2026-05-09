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

# ============================================================
# 4. control_db 스키마 — control 서비스가 사용 (운영 데이터)
#    - control_policy        : 운영자 조정 가능한 임계값
#    - control_policy_history: 정책 변경 이력 (트리거로 자동 기록)
#    - topology_nodes/lines/switches : 단선도 구성 정보
#
#    NOTE: control_history(=command_result)는 시계열 데이터로 분류되어
#          TimescaleDB 로 이동 (init_timescale.sh 참조).
#          정책: DB Writer 단일 게이트 (문서 04-services/db-writer.md)
#    멱등: CREATE TABLE IF NOT EXISTS / ON CONFLICT DO NOTHING
# ============================================================
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${CONTROL_DB}" <<-EOSQL
    -- ── control_policy (운영자 조정 가능 임계값) ──────────────
    CREATE TABLE IF NOT EXISTS control_policy (
        key             VARCHAR(64)     PRIMARY KEY,
        value           FLOAT           NOT NULL,
        unit            VARCHAR(16),
        description     TEXT,
        updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
        updated_by      VARCHAR(64)     NOT NULL DEFAULT 'system'
    );

    -- ── control_policy_history (정책 변경 이력) ───────────────
    CREATE TABLE IF NOT EXISTS control_policy_history (
        id              SERIAL          PRIMARY KEY,
        key             VARCHAR(64)     NOT NULL,
        old_value       FLOAT,
        new_value       FLOAT           NOT NULL,
        changed_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
        changed_by      VARCHAR(64)     NOT NULL DEFAULT 'system'
    );
    CREATE INDEX IF NOT EXISTS idx_policy_history_key ON control_policy_history (key, changed_at DESC);

    -- 정책 UPDATE 시 history 자동 기록 트리거
    CREATE OR REPLACE FUNCTION log_policy_change()
    RETURNS TRIGGER AS \$\$
    BEGIN
        INSERT INTO control_policy_history (key, old_value, new_value, changed_by)
        VALUES (NEW.key, OLD.value, NEW.value, NEW.updated_by);
        RETURN NEW;
    END;
    \$\$ LANGUAGE plpgsql;

    DROP TRIGGER IF EXISTS trg_policy_change ON control_policy;
    CREATE TRIGGER trg_policy_change
        AFTER UPDATE ON control_policy
        FOR EACH ROW EXECUTE FUNCTION log_policy_change();

    -- ── topology (단선도 구성) ────────────────────────────────
    -- EMS 가 토폴로지의 단일 진실 (Single Source of Truth).
    -- simulator 는 시뮬레이션 도구일 뿐 — 실 운영에선 EMS DB 가 정답.
    -- 운영자가 UI 로 노드/라인/스위치/좌표를 등록·수정한다.
    CREATE TABLE IF NOT EXISTS topology_nodes (
        id          SERIAL          PRIMARY KEY,
        site_id     VARCHAR(64)     NOT NULL,
        node_id     VARCHAR(64)     NOT NULL,
        node_type   VARCHAR(32)     NOT NULL,    -- GENERATION / STORAGE / LOAD / GRID / BUS
        device_id   VARCHAR(64),                  -- Redis state 의 device_id 와 매칭 (자원 텔레메트리 조회용)
        label       VARCHAR(128),
        x           FLOAT,                        -- 단선도 SVG 좌표 (운영자 편집 가능)
        y           FLOAT,
        UNIQUE (site_id, node_id)
    );

    CREATE TABLE IF NOT EXISTS topology_lines (
        id              SERIAL          PRIMARY KEY,
        site_id         VARCHAR(64)     NOT NULL,
        line_id         VARCHAR(64)     NOT NULL,
        from_node_id    VARCHAR(64)     NOT NULL,
        to_node_id      VARCHAR(64)     NOT NULL,
        rating_kw       FLOAT,                    -- 정격 용량
        UNIQUE (site_id, line_id)
    );

    CREATE TABLE IF NOT EXISTS topology_switches (
        id              SERIAL          PRIMARY KEY,
        site_id         VARCHAR(64)     NOT NULL,
        switch_id       VARCHAR(64)     NOT NULL,
        line_id         VARCHAR(64)     NOT NULL,
        switch_type     VARCHAR(32)     NOT NULL DEFAULT 'CB',  -- CB / DS / etc
        is_closed       BOOLEAN         NOT NULL DEFAULT true,
        controllable    BOOLEAN         NOT NULL DEFAULT true,  -- 원격 제어 가능 여부
        UNIQUE (site_id, switch_id)
    );

    -- ── PLANT-ALPHA 토폴로지 시드 (멱등) ──────────────────────────
    -- ID 규약은 simulator topology 와 동일하게 유지 (호환성).
    -- 좌표는 SVG 800×600 기준으로 배치.
    --   solar-01 (좌상)        diesel-01 (우상)
    --              \\          //
    --              ess-01 (중앙, 저장)
    --                  |
    --              load-01 (하단)
    INSERT INTO topology_nodes (site_id, node_id, node_type, device_id, label, x, y) VALUES
        ('PLANT-ALPHA', 'node-solar-edge-01',  'GENERATION', 'solar-01',  '태양광 발전 #1', 200, 100),
        ('PLANT-ALPHA', 'node-diesel-edge-01', 'GENERATION', 'diesel-01', '디젤 발전기 #1', 600, 100),
        ('PLANT-ALPHA', 'node-ess-edge-01',    'STORAGE',    'ess-01',    'ESS #1',         400, 300),
        ('PLANT-ALPHA', 'node-load-edge-01',   'LOAD',       'load-01',   '부하 #1',        400, 500)
    ON CONFLICT (site_id, node_id) DO NOTHING;

    INSERT INTO topology_lines (site_id, line_id, from_node_id, to_node_id, rating_kw) VALUES
        ('PLANT-ALPHA', 'line-solar01-ess01',  'node-solar-edge-01',  'node-ess-edge-01',  150),
        ('PLANT-ALPHA', 'line-diesel01-ess01', 'node-diesel-edge-01', 'node-ess-edge-01',  200),
        ('PLANT-ALPHA', 'line-ess01-load01',   'node-ess-edge-01',    'node-load-edge-01', 100)
    ON CONFLICT (site_id, line_id) DO NOTHING;

    INSERT INTO topology_switches (site_id, switch_id, line_id, switch_type, is_closed, controllable) VALUES
        ('PLANT-ALPHA', 'sw-solar01-ess01',  'line-solar01-ess01',  'CB', TRUE, TRUE),
        ('PLANT-ALPHA', 'sw-diesel01-ess01', 'line-diesel01-ess01', 'CB', TRUE, TRUE),
        ('PLANT-ALPHA', 'sw-ess01-load01',   'line-ess01-load01',   'CB', TRUE, TRUE)
    ON CONFLICT (site_id, switch_id) DO NOTHING;

    -- ── 정책 seed (멱등) ──────────────────────────────────────
    INSERT INTO control_policy (key, value, unit, description) VALUES
        ('SOC_LOW',                    20,    '%',    'ESS 방전 하한. 이 이하면 방전 금지'),
        ('SOC_HIGH',                   90,    '%',    'ESS 충전 상한. 이 이상이면 충전 금지'),
        ('SOC_CRITICAL_LOW',           5,     '%',    'ESS 긴급 방전 중단'),
        ('SOC_CRITICAL_HIGH',          98,    '%',    'ESS 긴급 충전 중단'),
        ('DIESEL_START_SOC',           20,    '%',    '디젤 기동 검토 SOC 기준'),
        ('DIESEL_STOP_NET_POWER',      10,    'kW',   '디젤 정지 검토 net_power 기준'),
        ('DIESEL_MIN_RUN_SECONDS',     300,   's',    '디젤 최소 운전 시간'),
        ('DIESEL_FUEL_LOW',            10,    '%',    '디젤 연료 부족 경고 기준'),
        ('DIESEL_FUEL_CRITICAL',       5,     '%',    '디젤 긴급 정지 기준'),
        ('LOAD_SHED_HOLD_SECONDS',     60,    's',    '부하 차단 후 복구 최소 대기 시간'),
        ('STATE_TTL',                  60,    's',    'Redis state 유효 시간'),
        ('CONTROL_INTERVAL',           1,     's',    'EMS 중앙 판단 루프 주기'),
        ('COMMS_TIMEOUT',              30,    's',    'Edge 통신 두절 판단 기준'),
        ('BATTERY_TEMP_MAX',           45,    '°C',   'ESS 배터리 온도 상한'),
        ('COOLANT_TEMP_MAX',           95,    '°C',   '디젤 냉각수 온도 상한'),
        ('GRID_FREQ_MIN',              58,    'Hz',   '계통 주파수 하한'),
        ('GRID_FREQ_MAX',              62,    'Hz',   '계통 주파수 상한'),
        ('LOAD_SHED_DEFAULT_PRIORITY', 3,     '',     '부하 등급 기본값 (1=필수/2=중요/3=일반/4=지연가능)'),
        ('ESS_POWER_LIMIT_KW',         50,    'kW',   'ESS 1대당 충방전 출력 상한'),
        ('LOAD_OVERLOAD_KW',           200,   'kW',   '부하 과부하 판단 절대값 기준'),
        -- SoC 임계 기반 단계적 부하 차단 (현업 정석 — 선제 보호).
        -- ESS 평균 SOC 가 임계 이하일 때 해당 등급 이상 부하 차단 권고 EVT-N-006 발행.
        ('SHED_SOC_TIER4',             25,    '%',    'Tier 4 (비필수/지연가능) 차단 시작 SOC'),
        ('SHED_SOC_TIER3',             20,    '%',    'Tier 3 (일반) 차단 시작 SOC'),
        ('SHED_SOC_TIER2',             15,    '%',    'Tier 2 (중요) 차단 시작 SOC. 이 이하면 Tier 1 만 유지.')
    ON CONFLICT (key) DO NOTHING;
EOSQL

# ============================================================
# 5. state_write_db 스키마 — state-processor 도메인 (state_meta)
#    - device_meta       : 등록된 device 메타데이터 + last_seen_at
#    - comms_health_log  : 통신 두절/복구 이력
#
#    NOTE: event_log(=event)는 시계열 데이터로 분류되어 TimescaleDB 로 이동.
#          (init_timescale.sh 참조)
#    INSERT 주체: DB Writer (단일 게이트, stream consumer)
#    SELECT 주체: state-processor (자기 DB)
# ============================================================
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "${STATE_DB}" <<-EOSQL
    -- ── device_meta (등록된 device 메타) ──────────────────────
    CREATE TABLE IF NOT EXISTS device_meta (
        device_id       VARCHAR(64)     PRIMARY KEY,
        site_id         VARCHAR(64)     NOT NULL,
        resource_type   VARCHAR(32)     NOT NULL,
        label           VARCHAR(128),
        rated_kw        FLOAT,
        capacity_kwh    FLOAT,           -- ESS 용량
        registered_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
        last_seen_at    TIMESTAMPTZ
    );
    CREATE INDEX IF NOT EXISTS idx_device_meta_site ON device_meta (site_id);
    CREATE INDEX IF NOT EXISTS idx_device_meta_type ON device_meta (resource_type);

    -- ── comms_health_log (통신 두절/복구 이력) ────────────────
    CREATE TABLE IF NOT EXISTS comms_health_log (
        id              SERIAL          PRIMARY KEY,
        time            TIMESTAMPTZ     NOT NULL,
        site_id         VARCHAR(64)     NOT NULL,
        device_id       VARCHAR(64)     NOT NULL,
        status          VARCHAR(16)     NOT NULL,   -- ok / disconnected / wire_fault
        duration_sec    INT                          -- disconnected→ok 복구 시 두절 지속 시간
    );
    CREATE INDEX IF NOT EXISTS idx_comms_health_device ON comms_health_log (device_id, time DESC);
    CREATE INDEX IF NOT EXISTS idx_comms_health_status ON comms_health_log (status, time DESC);
EOSQL

echo "===== init_postgres.sh 완료 ====="
echo "  - control_db   : control_policy(+history) / topology_* + 정책 seed 19개"
echo "  - state_write_db: device_meta / comms_health_log"
echo "  - ai_db        : (AI 팀이 자체 스키마 추가 예정)"
echo "  NOTE: 시계열(sensor_data/event_log/control_history)은 init_timescale.sh 참조"
