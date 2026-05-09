-- ============================================================
-- 시나리오: 도서지역(만재도) 하이브리드 마이크로그리드
-- 출처: 세영마이크로그리드.md
-- 자원 구성: PV(300kWp) + ESS(1~2MWh) + 디젤(백업) + Tier 부하 3개
-- 적용 DB: control_db (PostgreSQL)
-- ============================================================
-- 적용:
--   docker exec -i s14p31s305-ems-postgres-1 psql -U postgres -d control_db < manjae.sql
-- ============================================================

\echo '=== 만재도 시나리오 정책 적용 시작 ==='

-- ------------------------------------------------------------
-- 1. SOC 임계값 (세영 §5.1)
-- ------------------------------------------------------------
-- 0~10% 위급, 10~20% 경고, 20~90% 정상, 90~95% 주의, 95~100% 위험
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('SOC_CRITICAL_LOW',  10, '%', '[manjae] ESS 위급 — 방전 중단 + 디젤 긴급 기동'),
    ('SOC_LOW',           20, '%', '[manjae] ESS 경고 — 방전 제한 + 디젤 준비'),
    ('SOC_HIGH',          90, '%', '[manjae] 과충전 주의 — 충전 제한'),
    ('SOC_CRITICAL_HIGH', 95, '%', '[manjae] 위험 — 충전 중단 + PV curtailment')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- ------------------------------------------------------------
-- 2. 디젤 정책 (세영 §5.5, §6)
-- ------------------------------------------------------------
-- ESS SOC 가 SOC_LOW(20%) 도달 시 디젤 기동.
-- 디젤 정격 30kW (가사도 벤치마크 대비 만재도 규모 축소).
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('DIESEL_START_SOC',       20,    '%',   '[manjae] 디젤 기동 SOC 기준 (SOC_LOW 와 일치)'),
    ('DIESEL_STOP_NET_POWER',  10,    'kW',  '[manjae] 디젤 정지 net_power 기준 (잉여 10kW)'),
    ('DIESEL_MIN_RUN_SECONDS', 300,   's',   '[manjae] 디젤 최소 운전 시간 (5분 — 잦은 ON/OFF 방지)'),
    ('DIESEL_FUEL_LOW',        15,    '%',   '[manjae] 디젤 연료 부족 경고 (도서 보급 지연 대비)'),
    ('DIESEL_FUEL_CRITICAL',   8,     '%',   '[manjae] 디젤 긴급 정지 (연료 안전 마진)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- ------------------------------------------------------------
-- 3. ESS 정격 (세영 §1: ESS 1~2 MWh, PCS 25kW급 기준 → 우리 시뮬은 작은 ESS 가정)
-- ------------------------------------------------------------
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('ESS_POWER_LIMIT_KW', 50, 'kW', '[manjae] ESS PCS 출력 상한 (시뮬레이터 ESS 1대 기준)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- ------------------------------------------------------------
-- 4. 부하 우선순위 (세영 §5.2)
-- ------------------------------------------------------------
-- Tier 1 (필수: 의료/통신/급수) — 차단 안 함
-- Tier 2 (중요: 주거 기본/공용) — SOC 15% 이하 30% shed
-- Tier 3 (비필수: 에어컨/온수기) — SOC 25% 이하 50% shed, 15% 이하 100%
--
-- 우리 control 룰의 LOAD_PRIORITY_{device_id} 키와 매칭.
-- 숫자 작을수록 높은 우선순위 (= 마지막에 차단).
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('LOAD_SHED_DEFAULT_PRIORITY', 3, '', '[manjae] 신규 부하 기본 등급 (비필수)'),
    ('LOAD_SHED_HOLD_SECONDS',     60, 's', '[manjae] 부하 차단 후 복구 최소 대기 시간')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- 디바이스별 등급 (load edge 3개 추가 후 적용).
-- device_id 는 simulator-manager 가 만들어주는 이름과 일치시켜야 함.
-- device_id 는 simulator-manager 가 edge_id 끝에 '-01' suffix 를 자동 추가한다.
-- 즉 edge_id=load-residential 이면 device_id=load-residential-01.
-- LOAD_PRIORITY_{device_id} 키와 매칭되도록 키 이름 정확히 맞춤.
--
-- load-01 (기존 default load_edge-01) → Tier 1 (필수 — 의료/통신/급수 합산 부하 가정)
-- load-residential-01 → Tier 2 (주거)
-- load-comfort-01 → Tier 3 (에어컨/온수기)
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('LOAD_PRIORITY_load-01',              1, '', '[manjae] Tier 1 — 의료/통신/급수, 절대 차단 X'),
    ('LOAD_PRIORITY_load-residential-01',  2, '', '[manjae] Tier 2 — 주거 기본/공용, SOC 15%↓ 30% shed'),
    ('LOAD_PRIORITY_load-comfort-01',      3, '', '[manjae] Tier 3 — 에어컨/온수기, SOC 25%↓ 50% / 15%↓ 100%')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- SoC 임계 단계 차단 (만재도 §5.2 부하 우선순위 정책).
-- SOC 25% 이하 — 비필수 (Tier 4) 차단. 본 시나리오는 Tier 3 까지만 운영.
-- SOC 15% 이하 — Tier 2 (주거) 30% shed.
-- SOC 10% 이하 — Tier 1 만 유지.
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('SHED_SOC_TIER4', 25, '%', '[manjae] Tier 4 차단 시작 SOC (현재 시나리오 미사용)'),
    ('SHED_SOC_TIER3', 20, '%', '[manjae] Tier 3 (에어컨/온수기) 차단 시작 SOC'),
    ('SHED_SOC_TIER2', 15, '%', '[manjae] Tier 2 (주거) 차단 시작 SOC')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- ------------------------------------------------------------
-- 5. 통신/모니터링 정책 (세영 §5.3, §5.4)
-- ------------------------------------------------------------
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('STATE_TTL',         30,  's',  '[manjae] Redis state 유효 시간'),
    ('CONTROL_INTERVAL',  1,   's',  '[manjae] 제어 루프 주기'),
    ('COMMS_TIMEOUT',     30,  's',  '[manjae] Edge 통신 두절 판단 (도서 무선망 가정)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

-- ------------------------------------------------------------
-- 6. 안전 임계 (세영 §3.2 기상 제약 반영)
-- ------------------------------------------------------------
INSERT INTO control_policy (key, value, unit, description) VALUES
    ('BATTERY_TEMP_MAX',  45, '°C', '[manjae] ESS 배터리 온도 상한 (염해 환경 보수적)'),
    ('COOLANT_TEMP_MAX',  95, '°C', '[manjae] 디젤 냉각수 온도 상한'),
    ('GRID_FREQ_MIN',     58, 'Hz', '[manjae] 계통 주파수 하한'),
    ('GRID_FREQ_MAX',     62, 'Hz', '[manjae] 계통 주파수 상한'),
    ('LOAD_OVERLOAD_KW', 150, 'kW', '[manjae] 부하 과부하 절대값 (만재도 평균 95kW × 1.5)')
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    updated_at = NOW(),
    updated_by = 'scenario:manjae';

\echo '=== 만재도 시나리오 정책 적용 완료 ==='
\echo ''
\echo '적용 결과 확인:'
SELECT key, value, unit, updated_by
  FROM control_policy
  WHERE updated_by = 'scenario:manjae'
  ORDER BY key;
