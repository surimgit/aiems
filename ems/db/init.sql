-- ============================================================
-- TimescaleDB 초기화 스크립트
-- 시계열 테이블: sensor_data, event_log, control_history
-- 운영 테이블:   control_policy, control_policy_history
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 1. sensor_data
-- Redis Streams에서 1초 배치로 집계된 센서 데이터 저장
-- ============================================================
CREATE TABLE IF NOT EXISTS sensor_data (
    time            TIMESTAMPTZ     NOT NULL,
    site_id         VARCHAR(64)     NOT NULL,
    device_id       VARCHAR(64)     NOT NULL,
    resource_type   VARCHAR(32)     NOT NULL,  -- SOLAR / ESS / LOAD / DIESEL
    p_avg           FLOAT,                     -- 유효전력 평균 (kW)
    p_max           FLOAT,                     -- 유효전력 최대 (kW)
    p_min           FLOAT,                     -- 유효전력 최소 (kW)
    q_avg           FLOAT,                     -- 무효전력 평균 (kvar)
    v_avg           FLOAT,                     -- 전압 평균 (V)
    i_avg           FLOAT,                     -- 전류 평균 (A)
    f_avg           FLOAT,                     -- 주파수 평균 (Hz)
    pf_avg          FLOAT,                     -- 역률 평균
    soc             FLOAT,                     -- ESS 충전 상태 (%)
    kwh             FLOAT,                     -- 누적 전력량 (kWh)
    sample_count    INT             DEFAULT 1  -- 집계에 사용된 샘플 수
);

SELECT create_hypertable('sensor_data', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_sensor_data_device ON sensor_data (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_site   ON sensor_data (site_id, time DESC);

-- ============================================================
-- 2. event_log
-- 이상 감지 및 상태 변화 이벤트 저장
-- ============================================================
CREATE TABLE IF NOT EXISTS event_log (
    time            TIMESTAMPTZ     NOT NULL,
    site_id         VARCHAR(64)     NOT NULL,
    device_id       VARCHAR(64)     NOT NULL,
    resource_type   VARCHAR(32)     NOT NULL,
    event_type      VARCHAR(64)     NOT NULL,  -- EVT-N-001, EVT-E-001 등
    severity        VARCHAR(16)     NOT NULL,  -- INFO / WARNING / CRITICAL / EMERGENCY
    message         TEXT,
    payload         JSONB
);

SELECT create_hypertable('event_log', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_event_log_device   ON event_log (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_event_log_severity ON event_log (severity, time DESC);

-- ============================================================
-- 3. control_history
-- EMS가 발행한 제어 명령 이력 저장
-- ============================================================
CREATE TABLE IF NOT EXISTS control_history (
    time            TIMESTAMPTZ     NOT NULL,
    command_id      UUID            NOT NULL,
    site_id         VARCHAR(64)     NOT NULL,
    device_id       VARCHAR(64)     NOT NULL,
    resource_type   VARCHAR(32)     NOT NULL,
    command_type    VARCHAR(64)     NOT NULL,  -- ess_mode / diesel_command / set_curtailment 등
    payload         JSONB           NOT NULL,  -- 명령 상세 내용
    reason          TEXT,                      -- 판단 사유
    issued_by       VARCHAR(32)     NOT NULL DEFAULT 'rule',  -- rule / operator / ai
    ack_status      VARCHAR(16)     DEFAULT 'pending',        -- pending / accepted / rejected / timeout
    ack_time        TIMESTAMPTZ,
    verified        BOOLEAN         DEFAULT NULL              -- NULL=미검증, TRUE=물리반영, FALSE=미반영
);

SELECT create_hypertable('control_history', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_control_history_device     ON control_history (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_control_history_command_id ON control_history (command_id);

-- ============================================================
-- 4. control_policy
-- 관리자가 설정하는 제어 임계값 (서비스 재시작 없이 즉시 반영)
-- ============================================================
CREATE TABLE IF NOT EXISTS control_policy (
    key             VARCHAR(64)     PRIMARY KEY,
    value           FLOAT           NOT NULL,
    unit            VARCHAR(16),
    description     TEXT,
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_by      VARCHAR(64)     NOT NULL DEFAULT 'system'
);

-- 5. control_policy_history
-- control_policy 변경 이력 자동 기록
-- ============================================================
CREATE TABLE IF NOT EXISTS control_policy_history (
    id              SERIAL          PRIMARY KEY,
    key             VARCHAR(64)     NOT NULL,
    old_value       FLOAT,
    new_value       FLOAT           NOT NULL,
    changed_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    changed_by      VARCHAR(64)     NOT NULL DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_policy_history_key ON control_policy_history (key, changed_at DESC);

-- control_policy 변경 시 history 자동 기록 트리거
CREATE OR REPLACE FUNCTION log_policy_change()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO control_policy_history (key, old_value, new_value, changed_by)
    VALUES (NEW.key, OLD.value, NEW.value, NEW.updated_by);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_policy_change ON control_policy;
CREATE TRIGGER trg_policy_change
    AFTER UPDATE ON control_policy
    FOR EACH ROW EXECUTE FUNCTION log_policy_change();

-- ============================================================
-- 6. 기본 임계값 초기 데이터
-- ============================================================
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('SOC_LOW',                 20,     '%',    'ESS 방전 하한. 이 이하면 방전 금지'),
    ('SOC_HIGH',                90,     '%',    'ESS 충전 상한. 이 이상이면 충전 금지'),
    ('SOC_CRITICAL_LOW',        5,      '%',    'ESS 긴급 방전 중단. Edge 로컬 판단 기준'),
    ('SOC_CRITICAL_HIGH',       98,     '%',    'ESS 긴급 충전 중단. Edge 로컬 판단 기준'),
    ('DIESEL_START_SOC',        20,     '%',    '디젤 기동 검토 SOC 기준'),
    ('DIESEL_STOP_NET_POWER',   10,     'kW',   '디젤 정지 검토 net_power 기준'),
    ('DIESEL_MIN_RUN_SECONDS',  300,    's',    '디젤 최소 운전 시간'),
    ('DIESEL_FUEL_LOW',         10,     '%',    '디젤 연료 부족 경고 기준'),
    ('DIESEL_FUEL_CRITICAL',    5,      '%',    '디젤 긴급 정지 기준'),
    ('LOAD_SHED_HOLD_SECONDS',  60,     's',    '부하 차단 후 복구 최소 대기 시간'),
    ('STATE_TTL',               60,     's',    'Redis state 유효 시간'),
    ('CONTROL_INTERVAL',        1,      's',    'EMS 중앙 판단 루프 주기'),
    ('COMMS_TIMEOUT',           30,     's',    'Edge 통신 두절 판단 기준'),
    ('BATTERY_TEMP_MAX',        45,     '°C',   'ESS 배터리 온도 상한'),
    ('COOLANT_TEMP_MAX',        95,     '°C',   '디젤 냉각수 온도 상한'),
    ('GRID_FREQ_MIN',           58,     'Hz',   '계통 주파수 하한'),
    ('GRID_FREQ_MAX',           62,     'Hz',   '계통 주파수 상한'),
    ('LOAD_SHED_DEFAULT_PRIORITY', 3,  '',     '부하 등급 기본값 (1=필수/2=중요/3=일반/4=지연가능)')
ON CONFLICT (key) DO NOTHING;
