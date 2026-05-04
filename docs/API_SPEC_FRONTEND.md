# 프론트 ↔ EMS 백엔드 API 명세

본 문서는 프론트(`frontend/src/api/*.client.ts`)가 호출하는 API와 EMS 백엔드(`ems/state-processor`, `ems/control`, `simulator/topology`) 사이의 계약을 정의한다.

응답 필드명·타입은 `frontend/src/types/api-contracts.ts`를 정답으로 본다.

---

## 0. 라우팅 / 서비스 매핑

| Path prefix | 처리 서비스 | 포트(local) | 비고 |
|---|---|---|---|
| `/api/plants*` (resources/topology 제외) | state-processor | 5002 | |
| `/api/plants/{siteId}/topology` | topology | 8081 | nginx에서 프록시 |
| `/api/plants/{siteId}/resources` | state-processor | 5002 | **신규 구현 대상** |
| `/api/control/*` | control | 5003 | |
| `/api/ai/*` | ai-service | 5004 | 미구현 (placeholder) |

---

## 1. 신규 구현 대상

### 1.1 `GET /api/plants/{siteId}/resources` — Plant 자원 목록

**책임 서비스:** state-processor

**용도:** 대시보드에 발전·저장·부하 자원 카드를 띄우기 위해 사용. 토폴로지의 `nodes`와 동일 자원이지만 표현 형식이 다름(노드 위치/연결 정보 없이 자원 자체의 텔레메트리에 집중).

**응답 (200):** `ResourceDto[]`

```ts
interface ResourceDto {
  resource_id: string             // 예: "solar-01"
  resource_type: ResourceType     // 'LOAD' | 'SOLAR' | 'ESS' | 'DIESEL_GENERATOR' | 'SWITCH' | 'LINE' | 'GRID'
  name?: string                   // 표시용 라벨 (없으면 resource_id)
  status?: string                 // 'NORMAL' / 'WARNING' / 'EMERGENCY' / 'OFFLINE'
  comms_health?: string           // 'ok' / 'stale' / 'unknown'
  position?: 'OPEN' | 'CLOSED' | 'UNKNOWN'  // SWITCH 만 의미 있음
  controllable?: boolean          // SWITCH 만
  interlock_blocked?: boolean     // SWITCH 만
  from_node?: string              // LINE 만
  to_node?: string                // LINE 만
  flow_kw?: number                // LINE 만
  import_kw?: number              // GRID 만
  export_kw?: number              // GRID 만
  limit_kw?: number               // 정격 한계
  telemetry?: {
    p_kw?: number                 // 유효전력
    q_kvar?: number               // 무효전력
    v_volt?: number               // 전압
    i_amp?: number                // 전류
    f_hz?: number                 // 주파수
    pf?: number                   // 역률
    kwh?: number                  // 누적 전력량
    soc?: number                  // ESS만, %
    operating_mode?: string       // 'standby' / 'charge' / 'discharge' / 'generating' 등
  }
}
```

**구현 기준 (Redis state → ResourceDto 매핑):**

| ResourceDto 필드 | Redis state 출처 |
|---|---|
| `resource_id` | `device_id` |
| `resource_type` | `resource_type` (단, simulator의 `DIESEL` → DTO에선 `DIESEL_GENERATOR`로 변환) |
| `name` | `device_id` (별도 라벨이 없으면) |
| `status` | `emergency=true` → `EMERGENCY`, `comms_health=stale` → `OFFLINE`, else `NORMAL` |
| `comms_health` | `comms_health` |
| `position` | `reported_state.switch_state` (SWITCH만) |
| `controllable` | `reported_state.controllable` (SWITCH만) |
| `interlock_blocked` | `reported_state.interlock_blocked` (SWITCH만) |
| `telemetry.p_kw` | `reported_state.P` |
| `telemetry.q_kvar` | `reported_state.Q` |
| `telemetry.v_volt` | `reported_state.V` |
| `telemetry.i_amp` | `reported_state.I` |
| `telemetry.f_hz` | `reported_state.f` |
| `telemetry.pf` | `reported_state.PF` |
| `telemetry.kwh` | `reported_state.kwh_total` |
| `telemetry.soc` | `reported_state.SOC` |
| `telemetry.operating_mode` | `reported_state.operating_mode` |

**LINE / GRID 처리:**
- LINE은 topology API의 `lines[]`에서 가져와야 함. 본 엔드포인트에서는 LINE을 포함할지 별도 결정 필요. 우선 `device 4종 + switch 3종`만 반환.
- GRID는 현재 시뮬레이터에 없음 → 반환 안 함.

**예시 응답:**
```json
[
  {
    "resource_id": "solar-01",
    "resource_type": "SOLAR",
    "status": "NORMAL",
    "comms_health": "ok",
    "telemetry": {
      "p_kw": 624.54,
      "v_volt": 380.0,
      "i_amp": 1643.52,
      "kwh": 125.5
    }
  },
  {
    "resource_id": "ess-01",
    "resource_type": "ESS",
    "status": "NORMAL",
    "comms_health": "ok",
    "telemetry": {
      "p_kw": -50.0,
      "soc": 64.04,
      "operating_mode": "charge"
    }
  },
  {
    "resource_id": "sw-solar01-ess01",
    "resource_type": "SWITCH",
    "position": "CLOSED",
    "controllable": true,
    "interlock_blocked": false
  }
]
```

---

### 1.2 `GET /api/plants/{siteId}/topology` — 토폴로지 조회

**책임 서비스:** topology (포트 8081)

**현재 동작:** topology가 이미 `/api/topology`(siteId 무시) 제공 중. 프론트는 `/api/plants/{siteId}/topology`로 요청 → **gateway 또는 state-processor에서 프록시 처리** 또는 **topology에 라우트 추가** 둘 중 하나 선택 필요.

**응답 (200):** `TopologyDto`

```ts
interface TopologyDto {
  site_id: string
  nodes: TopologyNodeDto[]
  lines: TopologyLineDto[]
  switches?: TopologySwitchDto[]   // 옵션 (lines.switch에 이미 포함되긴 함)
}

interface TopologyNodeDto {
  node_id: string
  node_type: 'GENERATION' | 'STORAGE' | 'LOAD' | 'GRID' | 'BUS'
  resource_id: string             // 예: "solar-01"
  position: { x: number; y: number }   // ★ 현재 topology API 응답에 없음 — 추가 필요
  status: 'NORMAL' | 'WARNING' | 'EMERGENCY'
}

interface TopologyLineDto {
  line_id: string
  from_node_id: string
  to_node_id: string
  direction: 'FORWARD' | 'REVERSE' | 'BIDIRECTIONAL'   // ★ 현재 응답에 없음
  flow_kw: number
  status: 'NORMAL' | 'OPEN' | 'BLOCKED' | 'FAULT' | 'UNKNOWN'
}

interface TopologySwitchDto {
  switch_id: string
  line_id: string
  position: 'OPEN' | 'CLOSED'
  controllable: boolean
  interlock_blocked: boolean
}
```

**현재 topology 응답과 차이 — 보완 필요 항목:**

| DTO 필드 | 현재 응답 | 필요 동작 |
|---|---|---|
| `site_id` | 없음 | 라우트에서 받은 `siteId`를 박아주기 |
| `nodes[].position.x/y` | 없음 | DB `topology_nodes.x/y` 추가 또는 fallback 좌표 |
| `nodes[].status` | 없음 | Redis state의 `emergency` / `comms_health` 기반 산출 |
| `lines[].direction` | 없음 | `flow_kw > 0 → FORWARD`, `< 0 → REVERSE`, `0 → BIDIRECTIONAL` |
| `switches[]` | 없음 (lines.switch 안에 임베드) | top-level 배열 추가 |

---

## 2. 기존 구현된 엔드포인트 (확인용)

각 엔드포인트가 **DTO 스펙대로** 응답하는지 검증 필요. 본 절은 "이미 있다고 판단"되는 항목만 모은 것이며, 필드명/타입 검증은 각 항목별 PR에서 수행.

### 2.1 `GET /api/plants` — Plant 목록

**책임:** state-processor

**응답:** `PlantInfo[]`

```ts
interface PlantInfo {
  site_id: string
}
```

상태: ✅ 이미 구현. `_KNOWN_SITES` 기반.

### 2.2 `GET /api/plants/{siteId}/summary` — 전력 흐름 요약

**책임:** state-processor

**응답:** `PlantSummaryDto`

```ts
interface PlantSummaryDto {
  timestamp: string
  net_power_kw: number
  pv_power_kw: number
  ess_power_kw: number
  grid_power_kw: number      // ★ 현재 응답엔 diesel_power_kw 만 있고 grid는 없음
  load_power_kw: number
}
```

현재 응답: `site_id`, `timestamp`, `net_power_kw`, `pv_power_kw`, `ess_power_kw`, `load_power_kw`, `diesel_power_kw`, `ess_soc_avg`.
- 프론트는 `grid_power_kw`를 기대 → **현재 시뮬레이터에 GRID 없음 → 0 반환**.
- `diesel_power_kw`, `ess_soc_avg`는 추가 필드(프론트 무시 가능, 호환).

상태: ⚠️ `grid_power_kw` 추가 필요.

### 2.3 `GET /api/plants/{siteId}/state` — 디바이스 상태

**책임:** state-processor

**응답:** `PlantStateDto`

```ts
interface PlantStateDto {
  site_id: string
  timestamp: string
  ess_list?: EssStatusDto[]
  resources?: ResourceDto[]
  summary?: PlantSummaryDto
}
```

현재 응답: 디바이스 평탄 배열 (`device_id, P, SOC, …`).

상태: ❌ **스펙 불일치.** 현재는 단순 배열 반환, 프론트는 `{site_id, timestamp, ess_list, resources, summary}` 객체 기대.

→ 응답 형식 재구성 필요.

### 2.4 `GET /api/plants/{siteId}/events` — 이벤트 목록

**책임:** state-processor

**응답:** `EventDto[]`

```ts
interface EventDto {
  event_id: string
  event_code: string         // 예: 'EVT-N-013'
  severity: 'INFO' | 'WARNING' | 'ALARM' | 'EMERGENCY'
  message?: string
  timestamp: string
  site_id?: string
  resource_id?: string       // device_id 와 매핑
  trace_id?: string
  reason_code?: string
  payload?: Record<string, unknown>
}
```

현재 응답 필드 검증 필요. event_log 테이블 컬럼이 `event_type`이지만 DTO는 `event_code`. **필드명 매핑 필요.**

### 2.5 `GET /api/plants/{siteId}/alarms` — 알람 목록

**책임:** state-processor

**응답:** `AlarmData[]` (별도 정의)

상태: ✅ 구현됨. 프론트 type 추가 정의 후 검증.

### 2.6 `POST /api/control/operator-commands` — 운영자 명령

**책임:** control

**요청 / 응답:** 이미 검증 완료(통합 테스트 4번).

상태: ✅ 동작 확인.

### 2.7 `GET /api/control/commands` / `commands/{id}` — 명령 이력

**책임:** control

상태: ✅ 구현됨.

---

## 3. 미구현 (이번 PR 범위 밖)

| 엔드포인트 | 책임 서비스 | 비고 |
|---|---|---|
| `GET /api/plants/{siteId}/forecasts` | ai-service | AI 미구현 |
| `GET /api/plants/{siteId}/recommendations` | ai-service | AI 미구현 |
| `GET /api/plants/{siteId}/ai/latest` | ai-service | AI 미구현 |
| `POST /api/ai/inference-requests` | ai-service | AI 미구현 |
| `GET /api/ai/inference-results/{id}` | ai-service | AI 미구현 |
| `GET /api/ai/forecasts/{id}` | ai-service | AI 미구현 |
| `GET /api/ai/recommendations/{id}` | ai-service | AI 미구현 |
| `POST /api/control/recommendations/{id}/approve` | control | recommendation 모델 부재 |
| `POST /api/control/recommendations/{id}/reject` | control | recommendation 모델 부재 |

---

## 4. 작업 순서 제안

1. **`GET /api/plants/{siteId}/resources`** 신규 구현 (state-processor)
2. **`GET /api/plants/{siteId}/state`** 응답 형식 재구성 (state-processor)
3. **`GET /api/plants/{siteId}/summary`** `grid_power_kw=0` 추가 (state-processor)
4. **`GET /api/plants/{siteId}/events`** 필드명 매핑 (state-processor)
5. **`GET /api/plants/{siteId}/topology`** topology 서비스에 라우트 추가 + gateway 프록시 (topology + nginx)
6. AI / Recommendation 엔드포인트는 해당 서비스 구현 후 별도 PR.

---

## 5. 통합 검증 절차

각 엔드포인트 구현 후:

```bash
# 1) 컨테이너 재기동
cd c:/ems/S14P31S305-ems
docker compose up -d --build state-processor control

# 2) 응답 스펙 확인
curl -s http://localhost:5002/api/plants/PLANT-ALPHA/resources | python -m json.tool

# 3) 프론트 type과 비교 (필드명·타입)
#    → frontend/src/types/api-contracts.ts 의 ResourceDto 정확히 매칭되는지 수동 검증
```
