-- ============================================================
-- 시나리오: 부울경 좀비 아포칼립스 대피소 (영도 폐공장)
-- 출처: 좀비마이크로그리드.md
-- 자원 구성: PV(소형) + ESS(DIY 차량 배터리팩) + 4-Tier 부하 (디젤 없음)
-- 적용 DB: control_db (PostgreSQL)
-- ============================================================
-- 적용:
--   docker exec -i s14p31s305-ems-postgres-1 psql -U postgres -d control_db < zombie.sql
-- ============================================================

\echo '=== 좀비 시나리오 정책 적용 시작 ==='

-- ------------------------------------------------------------
-- 1. SOC 5단계 임계값 (좀비 §4.1)
-- ------------------------------------------------------------
-- 0~5%   임계 (울타리 제외 전부 차단)
-- 5~10%  위급 (의료 차단)
-- 10~20% 경고 (비상 절전)
-- 20~30% 주의 (수경재배 자동 차단)
-- 30~95% 정상
-- 95~100% 과충전 (PV curtailment)
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('SOC_CRITICAL_LOW',  10, '%', '[zombie] ESS 위급 — 의료장비 차단, 울타리 전력 집중'),
    ('SOC_LOW',           20, '%', '[zombie] ESS 경고 — 비상 절전 (통신/울타리만 유지)'),
    ('SOC_HIGH',          90, '%', '[zombie] 과충전 주의'),
    ('SOC_CRITICAL_HIGH', 95, '%', '[zombie] 위험 — 충전 중단, PV curtailment')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

-- ------------------------------------------------------------
-- 2. 디젤 정책 — 시나리오에선 디젤 없음 (대피소 환경)
-- ------------------------------------------------------------
-- 디젤 edge 자체가 없으므로 디젤 룰은 평가 대상 없음.
-- 정책은 default 값 유지 (혹시 운영 중 디젤 추가 시 대비).

-- ------------------------------------------------------------
-- 3. ESS 정격 (좀비 §3.2: DIY 차량 배터리팩, 작은 ESS)
-- ------------------------------------------------------------
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('ESS_POWER_LIMIT_KW', 30, 'kW', '[zombie] ESS PCS 출력 상한 (DIY 차량 배터리팩, 만재도 50kW 보다 작음)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

-- ------------------------------------------------------------
-- 4. 부하 4-Tier 우선순위 (좀비 §4.2)
-- ------------------------------------------------------------
-- Tier 1: 전기울타리 — 절대 차단 X (SOC 5%까지 유지)
-- Tier 2: 통신장비 — 차단 X (SOS 발신용)
-- Tier 3: 의료장비 — SOC 20% 이하 차단
-- Tier 4: 수경재배조명 — SOC 30% 이하 차단
--
-- device_id 는 simulator-manager 가 edge_id 끝에 -01 suffix 붙임:
--   edge_id=load-fence       → device_id=load-fence-01    (Tier 1)
--   edge_id=load-comms       → device_id=load-comms-01    (Tier 2)
--   edge_id=load-medical     → device_id=load-medical-01  (Tier 3)
--   edge_id=load-hydroponic  → device_id=load-hydroponic-01 (Tier 4)
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('LOAD_SHED_DEFAULT_PRIORITY', 4, '', '[zombie] 신규 부하 기본 등급 (가장 비필수)'),
    ('LOAD_SHED_HOLD_SECONDS',     30, 's', '[zombie] 부하 차단 후 복구 최소 대기 (대피소는 빠른 복구 필요)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

INSERT INTO control_policy (key, value, unit, description) VALUES
    ('LOAD_PRIORITY_load-fence-01',       1, '', '[zombie] Tier 1 — 전기울타리, 절대 차단 X (생존 직결)'),
    ('LOAD_PRIORITY_load-comms-01',       2, '', '[zombie] Tier 2 — 통신장비 (SOS 발신, 좀비 추적)'),
    ('LOAD_PRIORITY_load-medical-01',     3, '', '[zombie] Tier 3 — 의료장비, SOC 20%↓ 차단'),
    ('LOAD_PRIORITY_load-hydroponic-01',  4, '', '[zombie] Tier 4 — 수경재배조명, SOC 30%↓ 차단')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

-- SoC 임계 단계 차단 (좀비 §4.1 SOC 단계 정책).
-- SOC 30% 이하 — 수경재배(Tier 4) 자동 차단
-- SOC 20% 이하 — 의료(Tier 3) 차단
-- SOC 10% 이하 — 통신(Tier 2) 차단 (울타리만 유지)
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('SHED_SOC_TIER4', 30, '%', '[zombie] Tier 4 (수경재배) 차단 시작 SOC'),
    ('SHED_SOC_TIER3', 20, '%', '[zombie] Tier 3 (의료) 차단 시작 SOC'),
    ('SHED_SOC_TIER2', 10, '%', '[zombie] Tier 2 (통신) 차단 시작 SOC. 이 이하면 울타리만 유지.')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

-- ------------------------------------------------------------
-- 5. 통신/모니터링 (좀비 §4.5 응답 시간 1초 / 5초 / 30초)
-- ------------------------------------------------------------
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('STATE_TTL',         30, 's', '[zombie] Redis state 유효 시간'),
    ('CONTROL_INTERVAL',  1,  's', '[zombie] 제어 루프 주기 (1초 응답 위해)'),
    ('COMMS_TIMEOUT',     30, 's', '[zombie] Edge 통신 두절 판단')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

-- ------------------------------------------------------------
-- 6. 안전 임계 (좀비 §3 환경: 부산 해양성, 염분 강함)
-- ------------------------------------------------------------
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('BATTERY_TEMP_MAX',  40, '°C', '[zombie] DIY 배터리팩 온도 상한 (열화 우려로 보수적)'),
    ('LOAD_OVERLOAD_KW',  30, 'kW', '[zombie] 부하 과부하 절대값 (대피소 전체 ~10kW 가정)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:zombie';

\echo '=== 좀비 시나리오 정책 적용 완료 ==='
\echo ''
\echo '적용 결과:'
SELECT key, value, unit, updated_by
  FROM control_policy
  WHERE updated_by = 'scenario:zombie'
  ORDER BY key;
