# Control API 정의서

---

## 1. 목적

본 문서는 운영자 명령과 AI 추천 승인 요청을 Control 로 전달하는 API 경계를 정의한다.

Control API 는 Flask + flask-smorest + Marshmallow Schema 를 기준으로 구현하며, OpenAPI 문서는 코드에서 자동 생성한다.

API 계층은 외부 요청을 검증하고 usecase 로 전달하는 Input adapter 이다. 실제 제어 판단, 상태 조회, 정책 검증은 Control usecase 와 domain 에서 수행한다.

본 문서의 모든 엔드포인트는 **control 서비스 (포트 5003)** 가 제공한다.

---

## 2. 문서 제공 경로

| 항목 | 경로 |
| --- | --- |
| Swagger UI | `/docs` |
| OpenAPI JSON | `/openapi.json` |
| Health Check | `/health` |

---

## 3. 엔드포인트 목록

| Method | Path | 설명 | 구현 |
| --- | --- | --- | --- |
| POST | `/api/control/operator-commands` | 운영자 명령 생성 | ✅ |
| GET | `/api/control/commands/{command_id}` | 명령 상태 조회 | ✅ |
| GET | `/api/control/commands` | 명령 이력 조회 | ✅ |
| GET | `/api/control/policies` | 정책(임계값) 목록 조회 | ✅ |
| GET | `/api/control/policies/{key}` | 정책 단건 조회 | ✅ |
| PATCH | `/api/control/policies/{key}` | 정책 값 변경 | ✅ |
| GET | `/api/control/policies/{key}/history` | 정책 변경 이력 | ✅ |
| POST | `/api/control/recommendations/{recommendation_id}/approve` | AI 추천 승인 | ❌ AI 미구현 |
| POST | `/api/control/recommendations/{recommendation_id}/reject` | AI 추천 거부 | ❌ AI 미구현 |

### 3.1 API 경계 해설

Control API 의 기본 책임은 "제어 요청 처리(write)"이다.

동시에, 제어 요청 결과를 추적하기 위한 읽기 API(`GET /commands`)를 포함한다. 이 조회는 대시보드 상태 조회용 read API 가 아니라, Control 도메인 내부의 명령 추적 read 로 본다.

`control_history` 시계열 데이터는 TimescaleDB 에, `control_policy` 운영 데이터는 PostgreSQL `control_db` 에 저장된다.

---

## 4. 응답 스펙 (DTO)

### 4.1 `POST /api/control/operator-commands`

**요청:** `OperatorCommandRequest`

```ts
type CommandAction =
  | 'START_CHARGE'
  | 'STOP_CHARGE'
  | 'START_DISCHARGE'
  | 'STOP_DISCHARGE'
  | 'START_GENERATOR'
  | 'STOP_GENERATOR'
  | 'OPEN_SWITCH'
  | 'CLOSE_SWITCH'
  | 'SHED_LOAD'
  | 'RESTORE_LOAD'
  | 'SET_POWER_LIMIT'
  | 'STANDBY'

interface OperatorCommandRequest {
  site_id: string
  device_id: string                     // 또는 target_resource_id (동의어)
  resource_type: 'ESS' | 'DIESEL' | 'SOLAR' | 'LOAD' | 'SWITCH'
  action: CommandAction
  requested_by: string                  // operator-id 또는 자유 문자열
  reason?: string
  source_recommendation_id?: string | null
}
```

**예시:**
```json
{
  "site_id": "PLANT-ALPHA",
  "device_id": "ess-01",
  "resource_type": "ESS",
  "action": "START_CHARGE",
  "requested_by": "operator-01",
  "reason": "AI 추천 승인",
  "source_recommendation_id": "rec-001"
}
```

**응답 (202):** `ControlResult`

```ts
type CommandStatus = 'ACCEPTED' | 'REJECTED' | 'BLOCKED' | 'EXPIRED' | 'CREATED' | 'TIMEOUT'

interface ControlResult {
  command_id: string
  status: CommandStatus
  site_id: string
  target_resource_id: string            // device_id 의 별칭
  action: CommandAction
  created_at: string                    // ISO 8601
  // 추가 필드 (디버깅용, 프론트 무시 가능):
  resource_type?: string
  command_type?: string                 // 내부 명령 타입 (ess_mode / open / close 등)
  payload?: Record<string, unknown>
  reason?: string
  issued_by?: string
}
```

**예시:**
```json
{
  "command_id": "b1a45083-4ebc-4e25-bb3f-4bef920be076",
  "status": "ACCEPTED",
  "site_id": "PLANT-ALPHA",
  "target_resource_id": "ess-01",
  "action": "START_CHARGE",
  "created_at": "2026-04-20T10:30:00+09:00"
}
```

---

### 4.2 `GET /api/control/commands/{command_id}`

**응답 (200):** `ControlResult` (4.1 동일 형식)

**404:** 해당 command_id 없음.

---

### 4.3 `GET /api/control/commands`

**쿼리 파라미터 (모두 옵션):**
- `site_id` — 특정 plant 필터 (멀티 plant 환경)
- `device_id` — 특정 디바이스 필터
- `limit` — 기본 100, 최대 1000
- `offset` — 기본 0 (페이지네이션)

**응답:** `ControlResult[]` — `created_at DESC` 정렬.

**페이지네이션 예시:**
```
GET /api/control/commands?limit=50&offset=0    # 1페이지
GET /api/control/commands?limit=50&offset=50   # 2페이지
GET /api/control/commands?site_id=PLANT-ALPHA&device_id=ess-01&limit=20
```

**예시:**
```json
[
  {
    "command_id": "d48a2b62-eb99-4f98-85a3-2559132ad8b7",
    "status": "ACCEPTED",
    "site_id": "PLANT-ALPHA",
    "target_resource_id": "ess-01",
    "action": "START_CHARGE",
    "created_at": "2026-04-20T10:30:00+09:00",
    "resource_type": "ESS",
    "command_type": "ess_mode",
    "payload": { "mode": "charge", "target_power_kw": 50.0 },
    "reason": "external_net=618.5kW, SOC=71.027%",
    "issued_by": "rule"
  }
]
```

**저장소:** TimescaleDB `control_history` (시계열).

**필드 매핑 (DB → DTO):**
| DB | DTO |
|---|---|
| `ack_status` | `status` (대문자 변환) |
| `device_id` | `target_resource_id` |
| `time` | `created_at` |
| `(command_type, payload.mode)` | `action` (역추론) |

**action 역매핑 규칙:**
| command_type | mode/payload | action |
|---|---|---|
| `ess_mode` | `charge` | `START_CHARGE` |
| `ess_mode` | `discharge` | `START_DISCHARGE` |
| `ess_mode` | `standby` | `STANDBY` |
| `start` | - | `START_GENERATOR` |
| `stop` | - | `STOP_GENERATOR` |
| `open` | - | `OPEN_SWITCH` |
| `close` | - | `CLOSE_SWITCH` |
| `load_shed` | `reduction_ratio = 0` | `RESTORE_LOAD` |
| `load_shed` | `reduction_ratio > 0` | `SHED_LOAD` |
| `update_device_spec` | - | `SET_POWER_LIMIT` |

---

### 4.4 `GET /api/control/policies`

**응답:** `Policy[]`

```ts
interface Policy {
  key: string                          // 예: 'SOC_LOW'
  value: number
  unit: string | null
  description: string | null
  updated_at: string
  updated_by: string
}
```

**예시:**
```json
[
  {
    "key": "SOC_LOW",
    "value": 20.0,
    "unit": "%",
    "description": "ESS 방전 하한. 이 이하면 방전 금지",
    "updated_at": "2026-04-20T10:00:00+09:00",
    "updated_by": "system"
  }
]
```

---

### 4.5 `PATCH /api/control/policies/{key}`

**요청:**
```json
{ "value": 25.0, "updated_by": "operator-01" }
```

**응답 (200):** 변경된 `Policy`. 변경 이력은 `control_policy_history` 에 트리거로 자동 기록.

---

### 4.6 `GET /api/control/policies/{key}/history`

**쿼리 파라미터:**
- `limit` — 기본 50

**응답:** `PolicyHistory[]`

```ts
interface PolicyHistory {
  id: number
  key: string
  old_value: number | null
  new_value: number
  changed_at: string
  changed_by: string
}
```

---

## 5. Error Response

```json
{
  "error_code": "INTERLOCK_VIOLATION",
  "message": "Target resource is blocked by interlock.",
  "trace_id": "trc-20260420-0001",
  "details": {
    "site_id": "PLANT-ALPHA",
    "resource_id": "ess-01"
  }
}
```

---

## 6. Control 처리 절차

```text
요청 수신
→ Request Schema 검증
→ Redis Stream(mg:db:write) publish (control_history INSERT 위임 — db-writer 단일 게이트)
→ MQTT 명령 발행 ({plant_id}/{resource}/{device}/command)
→ ACK 추적 (mqtt_commander pending dict)
→ ACCEPTED → 10초 후 폐루프 검증 (Redis state 반영 확인)
→ 미반영 시 EVT-N-005 발행
```

---

## 7. 응답 상태 (CommandStatus)

| 상태 | 설명 |
| --- | --- |
| `ACCEPTED` | 요청 수락 (시뮬레이터/장비가 ACK 정상 응답) |
| `REJECTED` | 요청 거부 (장비가 명시적 거부) |
| `TIMEOUT` | ACK 응답 없음 (재시도 3회 후 최종 실패) |
| `BLOCKED` | 안전 또는 인터록 차단 |
| `EXPIRED` | 추천 또는 요청 만료 |
| `CREATED` | Command 생성 (초기 상태) |

---

## 8. 구현 기준

1. 요청/응답 Schema 는 Marshmallow Schema 로 정의한다.
2. Swagger UI 에 노출되지 않은 API 는 공식 API 로 인정하지 않는다.
3. 모든 제어 요청은 `command_id` 를 발급받아 추적 가능해야 한다.
4. 모든 실패 응답은 공통 Error Response 형식을 따른다.
5. AI 추천 승인도 일반 운영자 명령과 동일하게 Control 검증을 거친다.
6. `control` 서비스는 INSERT/UPDATE 를 직접 수행하지 않고 모두 `mg:db:write` 스트림으로 publish 한다 (DB Writer 단일 게이트 정책).

---

## 9. 결론

Control API 는 외부 요청을 최종 명령으로 변환하기 전에 검증하는 경계이다.

AI 추천 승인도 Control 검증을 통과해야만 실제 명령이 된다.
