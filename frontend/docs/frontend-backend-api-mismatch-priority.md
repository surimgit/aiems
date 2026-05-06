# 프론트엔드-백엔드 API 불일치 우선 수정 항목 (백엔드 전달용)

작성일: 2026-05-06  
대상: Frontend(Vue) / Backend(Flask smorest)

---

## 1) 결론 요약

현재 기준으로 **즉시 수정이 필요한 핵심(P0)**은 아래 3가지입니다.

1. 알람 ACK API 경로/메서드 통일
2. 프론트가 호출 중인 AI API 미구현 구간 정리
3. 공통 응답 형식(특히 에러 응답) 단일화

이 3개가 정리되지 않으면, 프론트 구현 진행 중 런타임 오류(404/405/파싱 실패)와 기능 공백이 반복됩니다.

---

## 2) P0 (즉시 수정 필요)

### P0-1. 알람 ACK API 경로/메서드 통일

#### 현재 상태
- 프론트 호출: `POST /api/plants/{site_id}/alarms/{alarm_id}/ack`
  - 근거: `frontend/src/api/dashboard.client.ts`
- 백엔드 코드 문맥: `PATCH /api/plants/{site_id}/alarms/{alarm_id}` 형태 ack 처리 흔적
  - 근거: `ems/state-processor/app/api.py` (`PlantAlarmDetailResource.patch`)

#### 문제
- 문서/프론트/백엔드 구현이 불일치하면 **404/405**가 발생할 수 있음.

#### 요청사항
- ACK API를 아래 중 하나로 확정하고 전면 통일:
  - A안: `POST /api/plants/{site_id}/alarms/{alarm_id}/ack`
  - B안: `PATCH /api/plants/{site_id}/alarms/{alarm_id}`
- 확정 후 반드시 동시 반영:
  1) Swagger/OpenAPI
  2) Flask route
  3) 프론트 API client

---

### P0-2. AI API 미구현 엔드포인트 처리

#### 현재 상태
- 프론트가 기대/호출하는 API:
  - `POST /api/ai/inference-requests`
  - `GET /api/ai/inference-results/{inference_id}`
  - `GET /api/ai/forecasts/{forecast_id}`
  - `GET /api/ai/recommendations/{recommendation_id}`
  - `GET /api/plants/{site_id}/ai/latest`
  - 근거: `frontend/src/api/ai.client.ts`
- `ai-api.md`에 위 항목 다수 **미구현**으로 명시

#### 문제
- 프론트 기능은 명세상 존재하지만 실제 호출 시 실패 가능.

#### 요청사항
- 아래 중 하나를 즉시 결정:
  - 1) 우선순위 높은 엔드포인트부터 실제 구현
  - 2) 임시 contract(빈 배열/기본 상태) 제공
  - 3) 미구현 API를 명시적으로 비활성 상태로 응답(표준 에러 코드)
- 최소 목표: 프론트가 런타임에서 예외 없이 fallback 가능하도록 계약 확정.

---

### P0-3. 공통 응답 형식 단일화 (성공/실패)

#### 현재 상태
- 정책 문서(`api-documentation-policy.md`)는 에러 응답 표준 강제:
  - `error_code`, `message`, `trace_id`, `details`
- 프론트 `http.ts`/`types/api.ts`는
  - direct payload
  - legacy `success/data` envelope
  를 동시에 처리 중

#### 문제
- 서비스별 응답 형태가 다르면 프론트 파싱/에러처리 분기가 계속 증가.

#### 요청사항
- 최종 계약 1개로 통일:
  - 성공 응답 포맷
  - 실패 응답 포맷
- `openapi.json` 기준으로 프론트 공통 클라이언트 파싱 규칙 확정.

---

## 3) P1 (이번 스프린트 내 정리 권장)

### P1-1. Control 목록 조회 쿼리 파라미터 통일

#### 현재 상태
- 프론트 쿼리: `site_id`, `page`, `page_size`
  - 근거: `frontend/src/api/control.client.ts`
- 백엔드 구현 중심: `device_id`, `limit`
  - 근거: `ems/control/app/api.py` (`/api/control/commands`)

#### 요청사항
- 쿼리 계약을 단일화:
  - `limit/offset` 또는 `page/page_size` 중 택1
- 정렬 기준(`time DESC`)도 문서에 고정.

---

### P1-2. 식별자 용어 통일 (`site_id` vs `plant_id`)

#### 현재 상태
- 문서/대화/코드에서 `site_id`, `plant_id` 혼용

#### 요청사항
- 외부 API 계약은 하나로 통일
- 권장: 현재 구현 다수가 `site_id`이므로 우선 `site_id` 유지 후 필요 시 마이그레이션 계획 수립.

---

### P1-3. Dashboard/AI 문서 구현 상태 동기화

#### 현재 상태
- `dashboard-api.md`에 AI 관련 경로가 일부 미구현 표기
- 프론트는 해당 API 사용 흐름 포함

#### 요청사항
- 배포 기준으로 "구현/미구현" 상태를 문서와 코드에서 일치시킬 것.

---

## 4) 정합 체크리스트 (백엔드 작업 완료 기준)

- [ ] 알람 ACK API 경로/메서드 단일화 및 Swagger 반영
- [ ] AI 미구현 API 처리 방침 확정(구현/임시응답/비활성 에러)
- [ ] 공통 성공/에러 응답 형식 단일화
- [ ] Control 목록 조회 쿼리 파라미터 단일화
- [ ] `site_id`/`plant_id` 용어 통일 기준 확정
- [ ] `dashboard-api.md`, `control-api.md`, `ai-api.md` 최신화

---

## 5) 참고 파일

### 프론트
- `frontend/src/api/dashboard.client.ts`
- `frontend/src/api/control.client.ts`
- `frontend/src/api/ai.client.ts`
- `frontend/src/api/http.ts`
- `frontend/src/types/api.ts`

### 백엔드
- `ems/state-processor/app/api.py`
- `ems/control/app/api.py`

### 문서
- `dashboard-api.md`
- `control-api.md`
- `ai-api.md`
- `api-documentation-policy.md`
- `flask-smorest-standard.md`

---

## 6) 전달 메모 (요약)

"프론트 개발은 현재 Dashboard/Control 일부는 진행 가능하지만, ACK API 불일치와 AI 미구현 경계 때문에 기능 완성이 막힙니다. 우선 P0 3개(ACK 통일, AI 계약 처리, 응답 형식 통일)부터 정리 부탁드립니다."
