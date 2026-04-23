-- Migration 002: event_log에 알람 조회/확인용 컬럼 추가
ALTER TABLE event_log ADD COLUMN IF NOT EXISTS alarm_id UUID DEFAULT gen_random_uuid();
ALTER TABLE event_log ADD COLUMN IF NOT EXISTS acknowledged BOOLEAN DEFAULT false;
ALTER TABLE event_log ADD COLUMN IF NOT EXISTS acked_at TIMESTAMPTZ DEFAULT NULL;
ALTER TABLE event_log ADD COLUMN IF NOT EXISTS acked_by VARCHAR(64) DEFAULT NULL;
CREATE INDEX IF NOT EXISTS idx_event_log_alarm_id ON event_log (alarm_id);
