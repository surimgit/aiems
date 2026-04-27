-- Migration 004: 누락된 policy seed 추가
-- 코드 내부 default로만 존재하던 키를 DB에 seed해서 operator가 API로 조정 가능하게 함.
-- 값은 기존 코드 default와 동일 — 기존 동작 변화 없음.

INSERT INTO control_policy (key, value, unit, description) VALUES
    ('ESS_POWER_LIMIT_KW', 50,  'kW', 'ESS 1대당 충방전 출력 상한'),
    ('LOAD_OVERLOAD_KW',   200, 'kW', '부하 과부하 판단 절대값 기준')
ON CONFLICT (key) DO NOTHING;
