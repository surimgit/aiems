# 프론트엔드-백엔드 API 정합 처리 결과 (인계용)

작성일: 2026-05-08
근거: `EMS실시간제어시스템설계문서/11-api/frontend-backend-api-mismatch-priority.md`
대상: Frontend(Vue) 팀

---

## 1. 결론

프론트팀이 요청한 **P0 4건 + P1 4건** 중 **AI 실제 구현을 제외한 7건 모두 처리 완료**.
프론트는 아래 변경사항 기준으로 client 코드 정리하면 됩니다.

---

## 2. 처리 결과 요약

| ID | 요청 | 처리 | 프론트 측 액션 |
|---|---|---|---|
| **P0-1** | 알람 ACK API 통일 | ✅ `POST /api/plants/{site_id}/alarms/{alarm_id}/ack` 신규 추가. 기존 `PATCH` 도 호환 유지. | 기존 client 그대로 가능. (POST `/ack` S14P31S305-ems/docs/FRONTEND_API_HANDOVER.md권장) |
| **P0-2** | AI API 미구현 처리 | ✅ 503 + 표준 Error Response (`error_code: FEATURE_UNAVAILABLE`) | 503 catch → fallback (placeholder UI) 분기 |
| **P0-3** | 공통 응답 형식 단일화 | ✅ Flask errorhandler 모든 에러 → 표준 형식 (`error_code, message, trace_id, details`) | legacy `success/data` envelope unwrap 제거 가능 |
| **P0-4** | `/resources` 응답 형태 | ✅ 이미 `ResourceDto[]` direct array | 변경 없음 |
| **P1-1** | Control 쿼리 파라미터 | ✅ `site_id`, `device_id`, `limit`, `offset` 모두 옵션 지원 | client 의 `page/page_size` → `limit/offset` 변경 |
| **P1-2** | `site_id` 통일 | ✅ 외부 API 모두 `site_id` 표준 | 변경 없음 (`plant_id` 사용 중이면 교체) |
| **P1-3** | 문서 동기화 | ✅ `dashboard-api.md`, `control-api.md` 최신화 | OpenAPI JSON 으로 타입 자동 생성 권장 |
| **P1-4** | 다국어 표시 | 🟡 **B안 결정** (`name_ko`, `name_en`). 실제 구현은 별도 PR. | 현 alias 시스템 유지. 추후 백엔드 응답에 `name_ko/name_en` 추가 시 override |

---

## 3. 변경 상세

### P0-1. 알람 ACK API

**신규 추가:**
```http
POST /api/plants/{site_id}/alarms/{alarm_id}/ack
Content-Type: application/json

{ "acked_by": "operator-01" }
```

**응답 (200):** `AlarmData` (acknowledged: true, acked_at, acked_by 채움)

**에러:**
- `404` 알람 없음
- `409` 30일 지난 압축된 알람 (TimescaleDB chunk 압축)
- `422` 요청 body 검증 실패

**기존 PATCH 유지:** 호환을 위해 `PATCH /api/plants/{site_id}/alarms/{alarm_id}` 도 동작. 신규 코드는 POST `/ack` 권장.

---

### P0-2. AI 미구현 엔드포인트

아래 엔드포인트들은 **503 + 표준 Error Response** 응답:

| 엔드포인트 |
|---|
| `GET /api/plants/{site_id}/forecasts` |
| `GET /api/plants/{site_id}/recommendations` |
| `GET /api/plants/{site_id}/ai/latest` |
| `POST /api/ai/inference-requests` |
| `GET /api/ai/inference-results/{id}` |
| `GET /api/ai/forecasts/{id}` |
| `GET /api/ai/recommendations/{id}` |

**응답 예시:**
```json
HTTP/1.1 503 Service Unavailable
Content-Type: application/json

{
  "error_code": "FEATURE_UNAVAILABLE",
  "message": "AI 서비스가 아직 활성화되지 않았습니다.",
  "trace_id": "5f8b4d2a-...",
  "details": {}
}
```

**프론트 처리 권장:**
```ts
try {
  const data = await getForecastList(siteId)
  // 정상 처리
} catch (e) {
  if (e.error_code === 'FEATURE_UNAVAILABLE') {
    // placeholder UI ("AI 서비스 준비 중")
  } else {
    // 일반 에러 처리
  }
}
```

---

### P0-3. 공통 응답 형식

**성공 응답:** 엔드포인트별 DTO 의 direct JSON (예: `ResourceDto[]`)

**실패 응답 (모든 4xx/5xx):**
```json
{
  "error_code": "INVALID_REQUEST" | "RESOURCE_NOT_FOUND" | "METHOD_NOT_ALLOWED" | "CONFLICT" | "VALIDATION_ERROR" | "FEATURE_UNAVAILABLE" | "INTERNAL_ERROR" | ...,
  "message": "사용자/개발자가 이해할 수 있는 설명",
  "trace_id": "uuid-...",
  "details": { /* 추가 정보 (validation errors 등) */ }
}
```

**에러 코드 매핑:**

| HTTP | error_code |
|---|---|
| 400 | `INVALID_REQUEST` |
| 404 | `RESOURCE_NOT_FOUND` |
| 405 | `METHOD_NOT_ALLOWED` |
| 409 | `CONFLICT` |
| 422 | `VALIDATION_ERROR` |
| 500 | `INTERNAL_ERROR` |
| 503 | `FEATURE_UNAVAILABLE` |

**프론트 액션:** legacy `{ success, data }` envelope unwrap 제거 가능. direct JSON 만 처리.

---

### P0-4. `/resources` 응답 형태

확정: **direct array `ResourceDto[]`**

```json
GET /api/plants/PLANT-ALPHA/resources

[
  { "resource_id": "solar-01", "resource_type": "SOLAR", ... },
  { "resource_id": "ess-01", "resource_type": "ESS", ... }
]
```

`{ resources: [...] }` envelope 반환 X.

---

### P1-1. Control 쿼리 파라미터

**최종 계약:**
```http
GET /api/control/commands?site_id={SITE}&device_id={DEVICE}&limit={N}&offset={M}
```

| 파라미터 | 타입 | 옵션 | 설명 |
|---|---|---|---|
| `site_id` | string | yes | 특정 plant 필터 (멀티 plant) |
| `device_id` | string | yes | 특정 디바이스 필터 |
| `limit` | int | yes (기본 100, 최대 1000) | 페이지 크기 |
| `offset` | int | yes (기본 0) | 페이지네이션 오프셋 |

**프론트 client 변경:**
```ts
// Before
listCommands({ site_id, page, page_size })

// After
listCommands({ site_id, device_id, limit, offset })
```

페이지 → offset 변환:
```ts
const offset = (page - 1) * page_size
const limit = page_size
```

---

### P1-2. `site_id` 통일

외부 API path / query / body / DTO 모두 **`site_id`** 사용. `plant_id` 사용 안 함.

| 용어 | 위치 |
|---|---|
| `site_id` | API path/query, DTO |
| `device_id` | EMS 내부 (사실상 외부에도 노출되지만 `target_resource_id` 별칭 권장) |
| `resource_id` | ResourceDto 표시용 식별자 |
| `target_resource_id` | ControlResult 응답에서 device_id 별칭 |

---

### P1-3. 문서 동기화

| 문서 | 상태 |
|---|---|
| `11-api/dashboard-api.md` | ✅ 최신 — 모든 엔드포인트 DTO 명세 + 응답 예시 |
| `11-api/control-api.md` | ✅ 최신 — operator-commands, commands, policies, recommendations |
| `11-api/ai-api.md` | ⚠️ AI 미구현 영역. 503 placeholder 명시. |

**OpenAPI JSON 기반 타입 자동 생성 권장:**
```bash
# state-processor (Dashboard API)
curl http://localhost:5002/openapi.json > openapi-dashboard.json

# control (Control API)
curl http://localhost:5003/openapi.json > openapi-control.json

# 프론트에서 typescript 타입 생성
npx openapi-typescript openapi-dashboard.json -o src/types/api-dashboard.ts
```

---

### P1-4. 다국어 — 결정만 완료

**결정: B안 (name_ko, name_en)**

선택 이유:
- 백엔드 응답에 다국어 같이 실어서 프론트 단순화
- 설비명은 자유 형식 (운영자가 새 자원 추가) → i18n key 매핑 어려움
- DB 컬럼 2개 추가만 하면 됨

**미구현 (별도 PR 진행 예정):**
- DB: `topology_nodes` 에 `label_ko`, `label_en` 컬럼 추가
- DTO: `ResourceDto`, `TopologyNodeDto` 에 `name_ko`, `name_en` 필드 추가
- 운영자 API: 노드 등록/수정 시 다국어 라벨 입력

**현재 프론트 측 권장:**
- 기존 alias 쿠키 시스템 (`ai-ems.resource-aliases`) **유지**.
- 백엔드 다국어 구현 완료 후 alias 는 override 용도로만 축소.

---

## 4. 빠른 검증 명령

```bash
# 1. 알람 ACK (P0-1)
curl -X POST http://localhost:5002/api/plants/PLANT-ALPHA/alarms/{ALARM_ID}/ack \
  -H "Content-Type: application/json" -d '{"acked_by":"operator-01"}'

# 2. AI 503 (P0-2)
curl -i http://localhost:5002/api/plants/PLANT-ALPHA/forecasts
# → HTTP/1.1 503 + { "error_code": "FEATURE_UNAVAILABLE", ... }

# 3. 공통 에러 (P0-3)
curl -i http://localhost:5002/api/plants/PLANT-ALPHA/alarms/INVALID-UUID
# → HTTP/1.1 404 + { "error_code": "RESOURCE_NOT_FOUND", "message": "...", "trace_id": "...", "details": {} }

# 4. /resources (P0-4)
curl http://localhost:5002/api/plants/PLANT-ALPHA/resources | jq 'type'
# → "array"

# 5. /commands 쿼리 (P1-1)
curl "http://localhost:5003/api/control/commands?site_id=PLANT-ALPHA&limit=10&offset=0"

# 6. Swagger UI (P1-3)
# state-processor: http://localhost:5002/docs
# control:         http://localhost:5003/docs
```

---

## 5. 미구현 영역 (별도 PR 또는 다음 스프린트)

| 항목 | 이유 |
|---|---|
| **AI 서비스 실제 구현** | AI 팀이 `ems/ai/train/` 모델 학습 후 inference 로직 구현. 백엔드는 placeholder 만 제공. |
| **P1-4 다국어 실제 구현** | DB 마이그레이션 + DTO 변경 작업 큼. 결정만 완료. |
| **WebSocket 실시간 푸시** | 현재 polling 으로 충분. 부하 증가 시 SSE/WebSocket 도입. |

---

## 6. 변경된 백엔드 파일 (참고용)

```
ems/state-processor/app/api.py
  - /alarms/{alarm_id}/ack POST 추가
  - /forecasts, /recommendations, /ai/latest 503 placeholder
  - errorhandler 400/404/405/409/422/500 표준 응답

ems/control/app/api.py
  - /commands 쿼리 site_id, offset 추가
  - errorhandler 표준화 (위와 동일)

EMS실시간제어시스템설계문서/11-api/control-api.md
  - §4.3 쿼리 파라미터 갱신

EMS실시간제어시스템설계문서/11-api/dashboard-api.md
  - §6.3 다국어 (P1-4) 결정 노트
```

---

## 7. 연락 / 후속

미정합 발견 시 백엔드 PR 채널로 보고. 백엔드는 ID 별 (P0-1 등) 로 추적.

다음 백엔드 작업 후보:
- AI 서비스 실제 구현 (AI 팀 협업)
- P1-4 다국어 DB/DTO 변경
- WebSocket/SSE 실시간 푸시 (성능 요구 시)
