# EMS Dashboard Frontend Architecture

## Overview

Vue 3 + TypeScript + TailwindCSS 기반 EMS(Energy Management System) 대시보드 프론트엔드 아키텍처입니다.

## 폴더별 역할

| 폴더 | 역할 |
|------|------|
| `app/` | 앱 셸, 라우터 설정 |
| `api/` | API 클라이언트 (dashboard/control/ai 분리) |
| `domain/` | 도메인 로직 (부호 규칙, 단위 변환, 모델) |
| `realtime/` | 실시간 데이터 (Polling, WebSocket) |
| `stores/` | Pinia 스토어 (상태 관리) |
| `features/` | 페이지를 위한 기능 조합 |
| `ui/` | UI 컴포넌트 (primitives, patterns) |
| `pages/` | Vue 페이지 컴포넌트 |
| `types/` | 공통 타입 정의 |

## API 경계 규칙

### 1. Dashboard API (조회 전용)
- **파일**: `api/dashboard.client.ts`
- **메서드**: GET만 허용
- **용도**: 전력 데이터, ESS 상태, 알람 조회

### 2. Control API (제어 + 명령 추적)
- **파일**: `api/control.client.ts`
- **메서드**: POST 중심 + 명령 상태/이력 조회 GET
- **용도**: 운영자 명령 생성, AI 추천 승인/거부, 명령 추적

### 3. AI API (조회/요청 전용)
- **파일**: `api/ai.client.ts`
- **메서드**: GET + inference request (POST)
- **용도**: 예측 조회, 권장 조치, AI 추론

## 페이지-피처-스토어-API 데이터 흐름

```
[API Client]
    ↓
[Pinia Store]
    ↓
[Feature Hook]
    ↓
[Page Component]
```

### 흐름 설명

1. **API Client** (`api/*.client.ts`): HTTP 요청 수행
2. **Pinia Store** (`stores/*/`): 상태 관리, API 호출 캡슐화
3. **Feature Hook** (`features/*/`): 스토어 조합, 뷰 로직 제공
4. **Page Component** (`pages/*.vue`): UI 렌더링만 담당

### 금지 사항

- **페이지에서 API 직접 호출 금지**: 항상 Feature를 통할 것
- **도메인 규칙 중복 구현 금지**: `domain/sign.ts`에서만 관리

## ESS 부호 규칙

`domain/sign.ts`에서 단일化管理:

- **양수(+)**: 방전 (Discharge) - ESS에서 외부로 전력送出
- **음수(-)**: 충전 (Charge) - 외부에서 ESS로 전력입력

## Phase 확장 계획

### Phase 1 (기초)
- [x] 폴더 구조 생성
- [x] API 클라이언트 기본 구현
- [x] Pinia 스토어 기본 구현
- [x] Page + Feature 연결

### Phase 2 (확장)
- [ ] 실제 API 연결
- [ ] 실시간 데이터 연동 (Polling/WebSocket)
- [ ] UI 컴포넌트 구현

### Phase 3 (고급)
- [ ] AI 예측 시각화
- [ ] 토폴로지 다이어그램
- [ ] 알람 실시간 알림

## 핵심 원칙

1. **관심사 분리**: API 유형별 클라이언트 분리
2. **단일 규칙**: ESS 부호 규칙은 `domain/sign.ts`에서만
3. **페이지 조합**: API 직접 호출 금지, Feature 통할 것
4. **비상 우선**: 전역 알람은 AppShell에서 항상 노출

## API Contract Source of Truth

- 프론트 API 계약의 기준 문서는 `ProjectDocs/11-api/*.md` 이다.
- Endpoint/HTTP Method/필수 파라미터는 위 문서를 우선한다.
- 프론트 코드의 임시 Mock 경로는 문서 계약과 다르면 즉시 리맵한다.
