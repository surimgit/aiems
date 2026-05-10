# OpenCode Quick Context (S14P31S305)

이 파일은 **빠른 작업 재개용 요약**이다. 매번 전체 폴더를 다시 분석하지 말고, 먼저 이 파일을 본다.

## 1) 프로젝트 한줄 요약
- 마이크로그리드 모니터링/제어 시스템
- FE: Vue3 + TS (`frontend/`)
- BE: Flask MSA (`ems/state-processor`, `ems/control`, `ems/ai`)

## 2) 작업 시 원칙 (Frontend)
- 데이터 흐름: `API -> Store -> Feature -> Page`
- `pages`에서 API 직접 호출 금지
- 브랜치 규칙: `fe/{작업유형}/{이슈번호}/{기능}`
- MR에는 **frontend 변경만** 포함 (ems/simulator pull 변경은 제외)

## 3) API 계약 Source of Truth 우선순위
1. **실행 중 백엔드 OpenAPI** (`/openapi.json`, `/docs`)
2. `11-api/*.md`
3. 기타 인계 문서 (`11-api/FRONTEND_API_HANDOVER.md`)

> 주의: `FRONTEND_API_HANDOVER.md`는 일부 항목이 현재 코드/문서와 불일치할 수 있음.

## 4) 현재 핵심 API 앵커 (non-map 기준)

### Dashboard (`11-api/dashboard-api.md`)
- `GET /api/plants/{site_id}/summary`
- `GET /api/plants/{site_id}/resources` → `ResourceDto[]` (direct array)
- `GET /api/plants/{site_id}/state`
- `GET /api/plants/{site_id}/alarms`
- Alarm ACK: `POST /api/plants/{site_id}/alarms/{alarm_id}/ack` (프론트 반영 완료)

### Control (`11-api/control-api.md`)
- `POST /api/control/operator-commands`
  - 요청 핵심: `site_id`, `device_id`, `resource_type`, `action`, `requested_by`
- `GET /api/control/commands`
  - 현재 프론트 반영 쿼리: `site_id`, `device_id`, `limit`, `offset`

### AI
- `GET /api/plants/{site_id}/forecasts|recommendations|ai/latest`는 placeholder/미구현 구간 존재
- FE는 503/`FEATURE_UNAVAILABLE` fallback 처리 적용 완료 (`[]` / `null` 반환)

## 5) 최근 확인된 중요 포인트
- handover 문서는 참고용이며, 최종 기준은 항상 서비스 `/docs` + `/openapi.json`
- control-api 문서와 런타임 구현이 어긋날 수 있어 commands query는 런타임 기준 재확인 필요
- MR 범위가 FE일 때는 ems/simulator 변경을 스테이징하지 않는다

## 6) 이번 세션에서 반영한 FE API 정합 변경 (완료)
- `frontend/src/api/http.ts`
  - `http.patch` 추가
- `frontend/src/api/dashboard.client.ts`
  - Alarm ACK 호출을 `POST /ack` + `{ acked_by }`로 정합화
- `frontend/src/stores/alarm/alarm.store.ts`
  - ACK 시 `DEFAULT_OPERATOR_ID` 전달
- `frontend/src/types/common.ts`
  - `OperatorCommandRequest`를 `device_id`, `resource_type` 중심으로 수정
- `frontend/src/api/control.client.ts`
  - list query를 `site_id`, `device_id`, `limit`, `offset`으로 확장
- `frontend/src/stores/control/control.store.ts`
  - `edgeId` 제거
  - history fetch를 `site_id + limit + offset` 기반으로 정리
  - submit/status 응답 target 매핑을 `target_resource_id ?? device_id`로 정규화
- `frontend/src/features/overview/components/right-panel/ControlPanel.vue`
  - submit payload를 `device_id` + `resource_type: 'ESS'`로 변경
- `frontend/src/api/ai.client.ts`
  - 503/`FEATURE_UNAVAILABLE` 임시 안전처리 적용 (forecast/recommendations/model status)
- `frontend/src/pages/OverviewPage.vue`
  - 이상 감지 배너 임시 preview alarm 제거 (실데이터만 사용)

## 7) 빠른 검증 루틴 (Frontend)
```bash
cd frontend
npm run typecheck
npm run build
```

## 8) 다음 작업 체크리스트
- [ ] docker 기반 통합 검증 (ACK / control submit / command history / AI 503 fallback)
- [ ] 최종 MR 전 `git diff --cached --name-only`로 frontend 파일만 포함 확인
- [ ] 백엔드 API 재동기화 시 `/docs` 기준으로 클라이언트 파라미터 재검토

## 9) 자주 보는 경로
- FE API 클라이언트: `frontend/src/api/*.ts`
- FE 스토어: `frontend/src/stores/**`
- 핵심 API 문서: `11-api/dashboard-api.md`, `11-api/control-api.md`, `11-api/ai-api.md`
- 불일치 관리: `11-api/frontend-backend-api-mismatch-priority.md`
