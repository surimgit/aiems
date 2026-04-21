-- ============================================================
-- 집계 뷰 및 압축 정책
-- 156: 1분 단위 집계 뷰
-- 157: 1시간 단위 집계 뷰
-- 158: TimescaleDB 압축 정책
-- ============================================================

-- ============================================================
-- 1. 1분 단위 집계 뷰 (156)
-- ============================================================
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

-- ============================================================
-- 2. 1시간 단위 집계 뷰 (157)
-- ============================================================
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

SELECT add_continuous_aggregate_policy('sensor_data_1h',
    start_offset => INTERVAL '2 hours',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

-- ============================================================
-- 3. 압축 정책 (158)
-- sensor_data: 7일 이상 된 데이터 압축
-- event_log: 30일 이상 된 데이터 압축
-- control_history: 30일 이상 된 데이터 압축
-- ============================================================
ALTER TABLE sensor_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, resource_type'
);

SELECT add_compression_policy('sensor_data',
    compress_after => INTERVAL '7 days',
    if_not_exists => TRUE
);

ALTER TABLE event_log SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, severity'
);

SELECT add_compression_policy('event_log',
    compress_after => INTERVAL '30 days',
    if_not_exists => TRUE
);

ALTER TABLE control_history SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'device_id, resource_type'
);

SELECT add_compression_policy('control_history',
    compress_after => INTERVAL '30 days',
    if_not_exists => TRUE
);

-- ============================================================
-- 4. 데이터 보존 정책 (90일 이후 자동 삭제)
-- ============================================================
SELECT add_retention_policy('sensor_data',
    drop_after => INTERVAL '90 days',
    if_not_exists => TRUE
);

SELECT add_retention_policy('event_log',
    drop_after => INTERVAL '90 days',
    if_not_exists => TRUE
);

SELECT add_retention_policy('control_history',
    drop_after => INTERVAL '180 days',
    if_not_exists => TRUE
);
