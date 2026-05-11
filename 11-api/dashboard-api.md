# Dashboard API 정의서

---

## 1. 목적

본 문서는 Dashboard가 EMS 상태를 조회하고 운영자 입력을 전달하기 위한 API 경계를 정의한다.

Dashboard API는 Flask + flask-smorest + Marshmallow Schema를 기준으로 구현하며, OpenAPI 문서는 코드에서 자동 생성한다.

Dashboard API는 UI가 필요한 조회 요청을 받는 Input adapter이다. 상태 계산, 제어 판단, AI 추론은 수행하지 않고 각 전담 서비스 또는 저장소 adapter를 통해 조회 결과를 조립한다.

본 문서의 모든 엔드포인트는 **state-processor 서비스 (포트 5002)** 가 제공한다. AI 관련(`/forecasts`, `/recommendations`, `/ai/*`) 만 별도 ai-service 가 제공한다 (미구현).

---

## 2. 문서 제공 경로

| 항목 | 경로 |
| --- | --- |
| Swagger UI | `/docs` |
| OpenAPI JSON | `/openapi.json` |
| Health Check | `/health` |

서비스별:
- state-processor: `http://state-processor:5002/docs` (Dashboard API 본체)
- control: `http://control:5003/docs` (Control API)
- db-writer: `http://db-writer:5005/docs`

---

## 3. API 책임

Dashboard API는 화면 표시와 운영자 입력 전달만 담당한다.

상태 계산, 제어 판단, AI 추론은 각 전담 서비스에서 수행한다.

---

## 4. 엔드포인트 목록

| Method | Path | 설명 | 구현 |
| --- | --- | --- | --- |
| GET | `/api/plants` | Plant 목록 조회 (멀티 플랜트 지원) | ✅ |
| GET | `/api/plants/{site_id}/summary` | Plant 요약 상태 | ✅ |
| GET | `/api/plants/{site_id}/resources` | 리소스 목록 (대시보드 카드) | ✅ |
| GET | `/api/plants/{site_id}/state` | 통합 상태 (summary + resources + ess_list) | ✅ |
| GET | `/api/plants/{site_id}/topology` | 토폴로지 (단선도 노드/라인/스위치) | ✅ |
| GET | `/api/plants/{site_id}/events` | 이벤트 목록 | ✅ |
| GET | `/api/plants/{site_id}/alarms` | 알람 목록 (WARNING+ 이벤트) | ✅ |
| POST | `/api/plants/{site_id}/alarms/{alarm_id}/ack` | 알람 ACK | ✅ |
| GET | `/api/plants/{site_id}/sensors` | 센서 시계열 (TimescaleDB) | ✅ |
| GET | `/api/plants/{site_id}/devices` | 디바이스 원시 상태 (디버깅) | ✅ |
| GET | `/api/plants/{site_id}/forecasts` | AI 예측 | ⚠️ 503 placeholder |
| GET | `/api/plants/{site_id}/recommendations` | AI 추천 | ⚠️ 503 placeholder |
| GET | `/api/plants/{site_id}/ai/latest` | 사이트 최신 AI 결과 묶음 | ⚠️ 503 placeholder |

---

## 5. 화면 갱신 기준

| 데이터 | 갱신 방식 |
| --- | --- |
| state summary | polling 또는 websocket |
| telemetry chart | polling 또는 websocket |
| event / alarm | websocket 우선 |
| recommendation | event 기반 반영 |
| topology | 정적 조회 + 상태 반영 |

---

## 6. 응답 스펙 (DTO)

### 6.1 `GET /api/plants`

**응답:** `PlantInfo[]`

```ts
interface PlantInfo {
  site_id: string
}
```

**예시:**
```json
[
  { "site_id": "PLANT-ALPHA" },
  { "site_id": "PLANT-BETA" }
]
```

**구현 노트:** `topology_nodes` 테이블의 distinct site_id 동적 조회. 결과 0개일 때만 환경변수 `SITE_ID` fallback.

---

### 6.2 `GET /api/plants/{site_id}/summary`

**응답:** `PlantSummaryDto`

```ts
interface PlantSummaryDto {
  site_id: string
  timestamp: string | null         // ISO 8601, 데이터 없으면 null
  net_power_kw: number             // 공급 - 수요 (양수=잉여, 음수=부족)
  pv_power_kw: number
  ess_power_kw: number             // ESS P 합 (방전+, 충전-)
  grid_power_kw: number            // 시뮬레이터 미보유 → 0 고정
  load_power_kw: number            // 절댓값 합산
  diesel_power_kw: number          // 추가 필드 (프론트 무시 가능)
  ess_soc_avg: number | null       // 추가 필드, ESS 평균 SOC
}
```

**예시:**
```json
{
  "site_id": "PLANT-ALPHA",
  "timestamp": "2026-04-20T10:30:00+09:00",
  "net_power_kw": 367.75,
  "pv_power_kw": 421.93,
  "ess_power_kw": 14.29,
  "grid_power_kw": 0.0,
  "load_power_kw": 68.48,
  "diesel_power_kw": 0.0,
  "ess_soc_avg": 85.02
}
```

---

### 6.3 `GET /api/plants/{site_id}/resources`

**응답:** `ResourceDto[]`

```ts
type ResourceType = 'LOAD' | 'SOLAR' | 'ESS' | 'DIESEL_GENERATOR' | 'SWITCH' | 'LINE' | 'GRID'
type ResourceStatus = 'NORMAL' | 'WARNING' | 'EMERGENCY' | 'OFFLINE'
type SwitchPosition = 'OPEN' | 'CLOSED' | 'UNKNOWN'

interface ResourceDto {
  resource_id: string                   // 예: "solar-01"
  resource_type: ResourceType
  name?: string
  status?: ResourceStatus
  comms_health?: string                 // 'ok' / 'stale' / 'unknown'
  // SWITCH 전용
  position?: SwitchPosition
  controllable?: boolean
  interlock_blocked?: boolean
  // device 전용
  telemetry?: {
    p_kw?: number
    q_kvar?: number
    v_volt?: number
    i_amp?: number
    f_hz?: number
    pf?: number
    kwh?: number
    soc?: number                         // ESS만
    operating_mode?: string              // 'standby' / 'charge' / 'discharge' / 'generating' 등
  }
}
```

**status 산출 규칙 (state-processor):**
| 조건 | status |
|---|---|
| `state.emergency = true` | `EMERGENCY` |
| `state.comms_health = 'stale'` | `OFFLINE` |
| 그 외 | `NORMAL` |

**예시 (device + switch 혼합):**
```json
[
  {
    "resource_id": "solar-01",
    "resource_type": "SOLAR",
    "name": "solar-01",
    "status": "NORMAL",
    "comms_health": "ok",
    "telemetry": {
      "p_kw": 624.54,
      "v_volt": 380.0,
      "i_amp": 1643.52,
      "f_hz": 60.0,
      "pf": 1.0
    }
  },
  {
    "resource_id": "ess-01",
    "resource_type": "ESS",
    "status": "NORMAL",
    "comms_health": "ok",
    "telemetry": {
      "p_kw": -50.0,
      "soc": 65.024,
      "operating_mode": "charge"
    }
  },
  {
    "resource_id": "sw-solar01-ess01",
    "resource_type": "SWITCH",
    "name": "sw-solar01-ess01",
    "status": "NORMAL",
    "position": "CLOSED",
    "controllable": true,
    "interlock_blocked": false
  }
]
```

**구현 노트:** 시뮬레이터의 `DIESEL` resource_type 은 응답 단계에서 `DIESEL_GENERATOR` 로 변환된다. LINE/GRID 는 별도 자원 모델이 없어 미반환.

**다국어 (P1-4 결정, 미구현):**
설비명 다국어는 **B안 — `name_ko`, `name_en` 2-필드 방식** 으로 결정.
- 응답 DTO 에 `name_ko`, `name_en` 추가 (옵션)
- DB `topology_nodes` 에 `label_ko`, `label_en` 컬럼 추가 필요
- 프론트는 locale 에 따라 선택 렌더, 미존재 시 `name` → `resource_id` 순 fallback
- 별도 PR (DB 마이그레이션 + DTO 변경 + 프론트 alias 시스템 축소) 로 진행 예정.

---

### 6.4 `GET /api/plants/{site_id}/state`

**응답:** `PlantStateDto` — 대시보드 메인 단일 호출용. summary + resources + ess_list 통합.

```ts
interface PlantStateDto {
  site_id: string
  timestamp: string | null
  ess_list?: EssStatusDto[]
  resources?: ResourceDto[]
  summary?: PlantSummaryDto
}

interface EssStatusDto {
  ess_id: string
  name?: string
  capacity_kwh: number
  max_power_kw: number
  soc: number
  soh?: number | null
  status: 'idle' | 'charging' | 'discharging' | 'fault'
  power_kw?: number
  updated_at?: string
}
```

**EssStatus.status 산출 규칙:**
| 조건 | status |
|---|---|
| `state.emergency = true` | `fault` |
| `operating_mode = 'charge'` 또는 `P < 0` | `charging` |
| `operating_mode = 'discharge'` 또는 `P > 0` | `discharging` |
| 그 외 | `idle` |

**예시:**
```json
{
  "site_id": "PLANT-ALPHA",
  "timestamp": "2026-04-20T10:30:00+09:00",
  "summary": { "...": "(6.2 PlantSummaryDto)" },
  "resources": [ "...(6.3 ResourceDto[])" ],
  "ess_list": [
    {
      "ess_id": "ess-01",
      "name": "ess-01",
      "capacity_kwh": 0.0,
      "max_power_kw": 0.0,
      "soc": 65.479,
      "soh": null,
      "status": "charging",
      "power_kw": -50.0,
      "updated_at": "2026-04-20T10:30:00+09:00"
    }
  ]
}
```

> `capacity_kwh` / `max_power_kw` 는 시뮬레이터가 telemetry 에 포함하면 채워진다. 미보유 시 0.

---

### 6.5 `GET /api/plants/{site_id}/topology`

**응답:** `TopologyDto`

```ts
type NodeType = 'GENERATION' | 'STORAGE' | 'LOAD' | 'GRID' | 'BUS'
type NodeStatus = 'NORMAL' | 'WARNING' | 'EMERGENCY'
type LineStatus = 'NORMAL' | 'OPEN' | 'BLOCKED' | 'FAULT' | 'UNKNOWN'
type LineDirection = 'FORWARD' | 'REVERSE' | 'BIDIRECTIONAL'
type SwitchPos = 'OPEN' | 'CLOSED'

interface TopologyDto {
  site_id: string
  nodes: TopologyNodeDto[]
  lines: TopologyLineDto[]
  switches: TopologySwitchDto[]
}

interface TopologyNodeDto {
  node_id: string
  node_type: NodeType
  resource_id: string | null
  position: { x: number; y: number }
  status: NodeStatus
}

interface TopologyLineDto {
  line_id: string
  from_node_id: string
  to_node_id: string
  direction: LineDirection
  flow_kw: number
  status: LineStatus
}

interface TopologySwitchDto {
  switch_id: string
  line_id: string
  position: SwitchPos
  controllable: boolean
  interlock_blocked: boolean
}
```

**산출 규칙:**

| 필드 | 산출 |
|---|---|
| `node.position` | `topology_nodes.x/y` (운영자 편집 가능) |
| `node.status` | `state.emergency` → EMERGENCY / `comms_health=stale` → WARNING / 그 외 NORMAL |
| `line.flow_kw` | from_node 의 device P 값 |
| `line.direction` | flow 부호: `>0.01 → FORWARD` / `<-0.01 → REVERSE` / 그 외 BIDIRECTIONAL |
| `line.status` | switch position 우선 (Redis state) — OPEN 이면 OPEN, 그 외 NORMAL |
| `switch.position` | Redis state 우선, 없으면 DB `is_closed` |
| `switch.controllable` | DB `topology_switches.controllable` |
| `switch.interlock_blocked` | Redis state `reported_state.interlock_blocked` |

**예시:**
```json
{
  "site_id": "PLANT-ALPHA",
  "nodes": [
    {
      "node_id": "node-solar-edge-01",
      "node_type": "GENERATION",
      "resource_id": "solar-01",
      "position": { "x": 200.0, "y": 100.0 },
      "status": "NORMAL"
    }
  ],
  "lines": [
    {
      "line_id": "line-solar01-ess01",
      "from_node_id": "node-solar-edge-01",
      "to_node_id": "node-ess-edge-01",
      "direction": "FORWARD",
      "flow_kw": 664.18,
      "status": "NORMAL"
    }
  ],
  "switches": [
    {
      "switch_id": "sw-solar01-ess01",
      "line_id": "line-solar01-ess01",
      "position": "CLOSED",
      "controllable": true,
      "interlock_blocked": false
    }
  ]
}
```

**저장소:** PostgreSQL `control_db` 의 `topology_nodes / topology_lines / topology_switches` (단일 진실).

---

### 6.6 `GET /api/plants/{site_id}/events`

**응답:** `EventDto[]`

```ts
type EventSeverity = 'INFO' | 'WARNING' | 'ALARM' | 'EMERGENCY'

interface EventDto {
  event_id: string                  // UUID (DB alarm_id)
  event_code: string                // 예: 'EVT-N-013'
  severity: EventSeverity           // DB CRITICAL → ALARM 으로 매핑
  message?: string
  timestamp: string                 // ISO 8601
  site_id?: string
  resource_id?: string              // device_id 매핑
  trace_id?: string                 // optional
  reason_code?: string              // optional
  payload?: Record<string, unknown>
}
```

**쿼리 파라미터:**
- `device_id` — 특정 디바이스 필터
- `severity` — INFO/WARNING/ALARM/EMERGENCY (대소문자 무관). `ALARM` 입력 시 DB 의 `CRITICAL` 매칭
- `limit` — 기본 100, 최대 1000

**예시:**
```json
[
  {
    "event_id": "ddb71270-6581-4403-9cda-f21e589d6be6",
    "event_code": "EVT-N-013",
    "severity": "WARNING",
    "message": "heartbeat 두절: solar-01 30초 이상 응답 없음",
    "timestamp": "2026-04-20T10:30:00+09:00",
    "site_id": "PLANT-ALPHA",
    "resource_id": "solar-01",
    "payload": { "elapsed_sec": 30 }
  }
]
```

**필드 매핑 (DB → DTO):**
| DB | DTO |
|---|---|
| `alarm_id` | `event_id` |
| `event_type` | `event_code` |
| `time` | `timestamp` |
| `device_id` | `resource_id` |
| `severity = CRITICAL` | `severity = ALARM` |

---

### 6.7 `GET /api/plants/{site_id}/alarms`

**응답:** `AlarmData[]` — WARNING 이상 이벤트만 필터.

```ts
type AlarmLevel = 'info' | 'warning' | 'critical'

interface AlarmData {
  alarm_id?: string
  level: AlarmLevel                 // 소문자
  code: string                      // 예: 'EVT-N-004'
  message: string
  ess_id?: string                   // ESS device 일 때만
  timestamp: string
  acknowledged?: boolean
  // 호환 추가 필드:
  site_id?: string
  resource_type?: string
  acked_at?: string
  acked_by?: string
}
```

**쿼리 파라미터:**
- `acknowledged` — `true`/`false`/미입력
- `severity` — WARNING/CRITICAL/EMERGENCY
- `limit` — 기본 100, 최대 1000

**level 매핑:**
| DB severity | DTO level |
|---|---|
| `WARNING` | `warning` |
| `CRITICAL` / `EMERGENCY` | `critical` |
| 그 외 | `info` |

**예시:**
```json
[
  {
    "alarm_id": "94db6c73-64b5-49aa-9537-519597b6f658",
    "level": "warning",
    "code": "EVT-N-004",
    "message": "STATE_TTL 초과: sw-ess01-load01 마지막 갱신 3661초 전",
    "ess_id": null,
    "timestamp": "2026-04-20T10:30:00+09:00",
    "acknowledged": false,
    "site_id": "PLANT-ALPHA",
    "resource_type": "SWITCH",
    "acked_at": null,
    "acked_by": null
  }
]
```

---

### 6.8 `POST /api/plants/{site_id}/alarms/{alarm_id}/ack`

**요청:**
```json
{ "acked_by": "operator-01" }
```

**응답 (200):** 동일 `AlarmData`. `acknowledged: true`, `acked_at`, `acked_by` 채워짐.

---

### 6.9 `GET /api/plants/{site_id}/sensors` (시계열 차트용)

**쿼리 파라미터:**
- `device_id` (필수)
- `from`, `to` — ISO 8601
- `interval` — `1s` (기본), `1m`, `5m`, `1h` 등 TimescaleDB time_bucket

**응답:** `SensorDataDto[]` — TimescaleDB `sensor_data` 1초 배치 집계 결과.

```ts
interface SensorDataDto {
  time: string
  site_id: string
  device_id: string
  resource_type: string
  p_avg?: number
  p_max?: number
  p_min?: number
  q_avg?: number
  v_avg?: number
  f_avg?: number
  pf_avg?: number
  soc?: number
  sample_count: number
}
```

---

### 6.10 `GET /api/plants/{site_id}/devices` (디버깅 / 내부용)

resources / state 의 가공 전 원시 Redis state 평탄 배열. 운영 화면에선 사용 비권장.

---

## 7. AI API 처리 현황

AI 관련 엔드포인트는 ai-service 미구현 상태이며, 프론트 런타임 에러 방지를 위해 503 placeholder 응답을 반환한다.

| Method | Path | 처리 서비스 | 상태 |
|---|---|---|---|
| GET | `/api/plants/{site_id}/forecasts` | state-processor (임시) | ⚠️ 503 placeholder |
| GET | `/api/plants/{site_id}/recommendations` | state-processor (임시) | ⚠️ 503 placeholder |
| GET | `/api/plants/{site_id}/ai/latest` | state-processor (임시) | ⚠️ 503 placeholder |
| POST | `/api/ai/inference-requests` | ai-service | ⚠️ 503 placeholder |
| GET | `/api/ai/inference-results/{id}` | ai-service | ⚠️ 503 placeholder |
| GET | `/api/ai/forecasts/{id}` | ai-service | ⚠️ 503 placeholder |
| GET | `/api/ai/recommendations/{id}` | ai-service | ⚠️ 503 placeholder |

**503 응답 형식:**
```json
{
  "error_code": "FEATURE_UNAVAILABLE",
  "message": "AI 서비스가 아직 활성화되지 않았습니다.",
  "trace_id": "<uuid>",
  "details": {}
}
```

> **기술 부채:** `/api/plants/...` 하위 AI 엔드포인트 3개는 S305 설계상 ai-service 담당이나, 현재 state-processor에 임시 배치. ai-service 구현 시 state-processor에서 제거 후 이관 필요.

ai-service 구현 후 `10-ai-contracts/*.md` 와 동기화.

---

## 8. 구현 기준

1. 조회 API 응답 Schema 는 Marshmallow Schema 로 정의한다.
2. 목록 조회 API 는 pagination, filter, sort 기준을 Schema 에 명시한다.
3. Dashboard API 는 내부 DB 테이블 구조를 직접 노출하지 않는다 — 필드명은 프론트 DTO 기준으로 매핑한다.
4. 실시간 갱신은 polling 또는 websocket 으로 제공할 수 있으나, 이벤트 원천은 Event Bus 흐름을 기준으로 한다.
5. 운영자 입력은 Control API 로 전달하며 Dashboard API 가 직접 제어 판단을 수행하지 않는다.
6. 시뮬레이터의 enum (`DIESEL`) 과 프론트 enum (`DIESEL_GENERATOR`) 이 다를 경우 응답 단계에서 변환한다.

---

## 9. 결론

Dashboard API 는 UI 가 필요한 데이터를 안정적으로 조회하는 경계이다.

서비스 내부 구현이나 DB 구조를 직접 노출하지 않으며, 프론트 DTO 와 1:1 매칭되도록 응답을 가공한다.
