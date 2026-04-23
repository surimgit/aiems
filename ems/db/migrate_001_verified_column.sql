-- Migration 001: control_history에 폐루프 검증 결과 컬럼 추가
-- NULL = 미검증, TRUE = 물리 반영 확인, FALSE = 미반영 (EVT-N-005 발행)

ALTER TABLE control_history
    ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT NULL;

-- 부하 등급 기본값 정책 추가
INSERT INTO control_policy (key, value, unit, description)
VALUES ('LOAD_SHED_DEFAULT_PRIORITY', 3, '', '부하 등급 기본값 (1=필수/2=중요/3=일반/4=지연가능)')
ON CONFLICT (key) DO NOTHING;
