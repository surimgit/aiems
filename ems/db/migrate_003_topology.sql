-- ============================================================
-- Migration 003: Topology tables
-- 단선도 구성 정보 (노드, 선로, 개폐기)
-- ============================================================

-- ── 1. topology_nodes ──────────────────────────────────────
-- 발전소 내 전기적 노드 (장비 또는 버스바)
CREATE TABLE IF NOT EXISTS topology_nodes (
    id              SERIAL          PRIMARY KEY,
    site_id         VARCHAR(64)     NOT NULL,
    node_id         VARCHAR(64)     NOT NULL,   -- e.g. "ess-01", "busbar-main"
    node_type       VARCHAR(32)     NOT NULL,   -- SOLAR / ESS / DIESEL / LOAD / BUS
    device_id       VARCHAR(64),               -- 실시간 상태 조회용 (state:{site_id}:{device_id})
    label           VARCHAR(128),
    x               FLOAT,                     -- 단선도 UI 좌표
    y               FLOAT,
    UNIQUE (site_id, node_id)
);

-- ── 2. topology_lines ──────────────────────────────────────
-- 노드 간 전력 선로
CREATE TABLE IF NOT EXISTS topology_lines (
    id              SERIAL          PRIMARY KEY,
    site_id         VARCHAR(64)     NOT NULL,
    line_id         VARCHAR(64)     NOT NULL,
    from_node_id    VARCHAR(64)     NOT NULL,
    to_node_id      VARCHAR(64)     NOT NULL,
    rating_kw       FLOAT,                     -- 선로 정격 용량 (kW)
    UNIQUE (site_id, line_id)
);

-- ── 3. topology_switches ───────────────────────────────────
-- 개폐기 (차단기 / 단로기)
CREATE TABLE IF NOT EXISTS topology_switches (
    id              SERIAL          PRIMARY KEY,
    site_id         VARCHAR(64)     NOT NULL,
    switch_id       VARCHAR(64)     NOT NULL,
    line_id         VARCHAR(64)     NOT NULL,   -- 어느 선로에 삽입됐는지
    switch_type     VARCHAR(32)     NOT NULL DEFAULT 'CB',  -- CB / DS / MCB
    is_closed       BOOLEAN         NOT NULL DEFAULT true,
    UNIQUE (site_id, switch_id)
);

-- ── 4. PLANT-ALPHA 초기 토폴로지 ───────────────────────────

-- 노드
INSERT INTO topology_nodes (site_id, node_id, node_type, device_id, label, x, y) VALUES
    ('PLANT-ALPHA', 'busbar-main',  'BUS',    NULL,         '주 버스바',    400, 200),
    ('PLANT-ALPHA', 'solar-01',     'SOLAR',  'solar-01',   '태양광 1',     100, 50),
    ('PLANT-ALPHA', 'solar-02',     'SOLAR',  'solar-02',   '태양광 2',     250, 50),
    ('PLANT-ALPHA', 'ess-01',       'ESS',    'ess-01',     'ESS 1',        100, 350),
    ('PLANT-ALPHA', 'ess-02',       'ESS',    'ess-02',     'ESS 2',        250, 350),
    ('PLANT-ALPHA', 'ess-03',       'ESS',    'ess-03',     'ESS 3',        400, 350),
    ('PLANT-ALPHA', 'ess-04',       'ESS',    'ess-04',     'ESS 4',        550, 350),
    ('PLANT-ALPHA', 'diesel-01',    'DIESEL', 'diesel-01',  '디젤 발전기',   700, 50),
    ('PLANT-ALPHA', 'load-01',      'LOAD',   'load-01',    '부하 1',        550, 50),
    ('PLANT-ALPHA', 'load-02',      'LOAD',   'load-02',    '부하 2',        700, 200),
    ('PLANT-ALPHA', 'load-03',      'LOAD',   'load-03',    '부하 3',        700, 350)
ON CONFLICT (site_id, node_id) DO NOTHING;

-- 선로
INSERT INTO topology_lines (site_id, line_id, from_node_id, to_node_id, rating_kw) VALUES
    ('PLANT-ALPHA', 'line-solar01-bus',   'solar-01',   'busbar-main', 100),
    ('PLANT-ALPHA', 'line-solar02-bus',   'solar-02',   'busbar-main', 80),
    ('PLANT-ALPHA', 'line-ess01-bus',     'ess-01',     'busbar-main', 42),
    ('PLANT-ALPHA', 'line-ess02-bus',     'ess-02',     'busbar-main', 38),
    ('PLANT-ALPHA', 'line-ess03-bus',     'ess-03',     'busbar-main', 45),
    ('PLANT-ALPHA', 'line-ess04-bus',     'ess-04',     'busbar-main', 36),
    ('PLANT-ALPHA', 'line-diesel01-bus',  'diesel-01',  'busbar-main', 150),
    ('PLANT-ALPHA', 'line-bus-load01',    'busbar-main','load-01',     50),
    ('PLANT-ALPHA', 'line-bus-load02',    'busbar-main','load-02',     50),
    ('PLANT-ALPHA', 'line-bus-load03',    'busbar-main','load-03',     50)
ON CONFLICT (site_id, line_id) DO NOTHING;

-- 개폐기 (각 선로에 차단기 1개씩)
INSERT INTO topology_switches (site_id, switch_id, line_id, switch_type, is_closed) VALUES
    ('PLANT-ALPHA', 'cb-solar01',   'line-solar01-bus',  'CB', true),
    ('PLANT-ALPHA', 'cb-solar02',   'line-solar02-bus',  'CB', true),
    ('PLANT-ALPHA', 'cb-ess01',     'line-ess01-bus',    'CB', true),
    ('PLANT-ALPHA', 'cb-ess02',     'line-ess02-bus',    'CB', true),
    ('PLANT-ALPHA', 'cb-ess03',     'line-ess03-bus',    'CB', true),
    ('PLANT-ALPHA', 'cb-ess04',     'line-ess04-bus',    'CB', true),
    ('PLANT-ALPHA', 'cb-diesel01',  'line-diesel01-bus', 'CB', true),
    ('PLANT-ALPHA', 'cb-load01',    'line-bus-load01',   'CB', true),
    ('PLANT-ALPHA', 'cb-load02',    'line-bus-load02',   'CB', true),
    ('PLANT-ALPHA', 'cb-load03',    'line-bus-load03',   'CB', true)
ON CONFLICT (site_id, switch_id) DO NOTHING;
