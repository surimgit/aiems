# S14P31S305 Frontend 통합 STD (Software Technical Design)

## 1. 문서 목적
- 본 문서는 `frontend` 전체의 기술 설계를 단일 문서로 고정한다.
- 설계/개발/리뷰/배포 시 판단 기준을 한 곳에서 확인할 수 있도록 한다.
- 페이지 단위가 아닌 **아키텍처 + 상태 + API + UI + 운영**까지 포함한다.

---

## 2. 범위 / 비범위

### 2.1 범위
- Vue3 + TypeScript + Pinia + Tailwind 기반 프론트엔드 전체
- `src/app`, `src/api`, `src/stores`, `src/features`, `src/pages`, `src/domain`, `src/realtime`, `src/ui`, `src/types`
- Overview 메인 대시보드(16:9 관제형)

### 2.2 비범위
- 백엔드 도메인 로직 상세
- 인프라 서버 구축 절차 상세(해당 문서는 infra 문서 참조)
- ML 모델 설계 상세

---

## 3. 기술 스택 및 실행 표준
- Framework: Vue 3
- Language: TypeScript
- State: Pinia
- Build: Vite
- Style: TailwindCSS (+ scoped style)

### 3.1 필수 스크립트
- `npm run dev`: 개발 서버
- `npm run typecheck`: 타입 검증
- `npm run build`: 배포 빌드

### 3.2 운영 원칙
- `typecheck/build` 통과 상태를 기준으로 기능 완료 판단
- `dist`는 빌드 산출물이며 버전관리 대상에서 제외

---

## 4. 아키텍처 원칙 (SSOT)

### 4.1 데이터 흐름
```txt
API Client -> Store(Pinia) -> Feature Composable -> Page -> UI Components
```

### 4.2 계층 책임
- `pages/`: 화면 조립만 담당 (API 직접 호출 금지)
- `features/`: 화면 단위 뷰 로직/조합
- `stores/`: 상태/액션/서버 통신 오케스트레이션
- `api/`: HTTP 계약 호출 캡슐화
- `domain/`: 부호/단위/매핑 같은 규칙 처리
- `ui/`: 재사용 가능한 프레젠테이션 컴포넌트

### 4.3 금지 사항
- Page에서 API 직접 호출
- 도메인 규칙 중복 구현
- 타입 무시(`as any`, ts-ignore 계열)

---

## 5. 디렉터리 구조
```txt
frontend/
  docs/
  src/
    app/       # AppShell, router, config
    api/       # *.client.ts, http.ts
    stores/    # dashboard/alarm/control/ai
    features/  # overview/topology/... 기능별
    pages/     # Overview/Detail/... 라우트 페이지
    domain/    # sign, units, mappers
    realtime/  # websocket/polling 타입/소스
    types/     # common, api-contracts
    ui/        # primitive/pattern
```

---

## 6. 라우팅/화면 정책
- 기본 메인 화면은 `OverviewPage.vue`
- 상세 페이지들은 기능별 분리
- 관제 운영 기준 주요 상태 판단은 Overview에서 즉시 가능해야 함

---

## 7. 상태 관리(Pinia) 설계

### 7.1 핵심 Store
- `dashboard.store`: 전력요약, 토폴로지, ESS/리소스
- `alarm.store`: 알람 목록/필터/ack
- `control.store`: 명령 생성/상태/이력
- `ai.store`: 예측/추천/모델상태

### 7.2 상태 설계 규칙
- 선택 설비 상태(`selectedEssId`)는 전역 일관 상태로 유지
- UI에서 숫자 포맷 시 항상 값 검증 후 렌더
- 낙관적 업데이트 시 실패 롤백 정책 필수

---

## 8. API 계약 및 오류 처리

### 8.1 API 원칙
- API 계약은 `types/api-contracts.ts` 기준
- UI 타입은 `types/common.ts`로 매핑
- `api/*.client.ts`에서 mapper를 통해 DTO -> UI 타입 변환

### 8.2 오류 처리
- 네트워크/서버 오류는 Store 레벨 `error` 상태로 통합
- 사용자 노출은 패널/위젯 상태 메시지 또는 토스트로 처리
- 렌더 단계에서 예외가 발생하지 않도록 fallback 문자열 사용 (`데이터 없음`)

---

## 9. 실시간 처리(realtime)
- polling/websocket은 공통 타입(`realtime/types.ts`) 기반
- 실시간 이벤트 반영 시 기존 store 상태와 충돌하지 않도록 단일 진입점 유지
- polling 중단 로직(`stopPolling`)은 누수 방지 관점에서 필수 구현 대상

---

## 10. UI/디자인 시스템 통합 규칙

### 10.1 기본 컨셉
- SCADA 관제형: 빠른 상태 판단, 낮은 시각적 노이즈
- 과도한 네온/장식 금지, 기능 중심 표시

### 10.2 컬러 제한
- 배경: `#0B1420`, `#0F1B2D`, `#132338`
- 상태: 정상 `#22C55E`, 경고 `#F59E0B`, 이상 `#EF4444`
- 강조: `#3B82F6`

### 10.3 카드/패널
- radius 12~16px
- border `rgba(255,255,255,0.1)`
- 패널 간 간격 20~24px
- 외곽 여백 32px+

---

## 11. Overview 메인 대시보드 표준

### 11.1 레이아웃
```txt
Header
Main Topology + Right Panel
Bottom 3 Panels (AI 예측 | KPI 요약 | AI 성과)
```

### 11.2 확정 인터랙션
- 우측 패널 기본: 닫힘
- tablet: 우측 패널 오버레이
- node 클릭: `selected-resource` 자동 오픈
- 패널 닫기: X + ESC
- 패널 열린 상태에서도 토폴로지 클릭 허용
- active 아이콘: 파란 아웃라인
- 패널 오픈 애니메이션: 180ms

### 11.3 Right Panel 모드
- `alarm`, `recent-command`, `country-language`, `selected-resource`, `control`, `load-usage`
- single-active-mode 유지

### 11.4 모드별 세부 규칙
- 알람 Top3: 심각도 우선 + 최신순
- 알람 ack 후: 목록 유지 + 확인됨 배지
- 최근 명령: 기본 8개
- 명령 결과 색상: 실패만 빨강 강조
- 국가선택: 검색 상시 노출
  - tablet 8개(2x4)
  - monitor 12개(3x4)
  - wall 20개(4x5)

---

## 12. 컴포넌트 구조 표 (요약)

| 컴포넌트 | 책임 | Props | Events | State 연계 |
|---|---|---|---|---|
| OverviewPage | 전체 오케스트레이션 | - | - | mode/rightPanel/viewport |
| TopBarKpiStrip | 헤더/아이콘 트리거 | powerSummary, activeAlarmCount | toggle-mode | activeIcon |
| DashboardShell | 레이아웃 셸 | mode, panelOpen | - | panel-open class |
| TopologyStage | 토폴로지 컨테이너 | topology | select-node | selected node |
| TopologyNodeLayer | 노드 렌더 | nodes | select-node | highlight |
| TopologyLineLayer | 흐름선 렌더 | lines | - | line style |
| RightPanelShell | 우측 공통 셸 | title | close | open/close transition |
| AlarmTopPanel | 알람 Top3 표시 | store 기반 | ack | severity/ack |
| RecentCommandPanel | 최근 명령 표시 | store 기반 | view-all | list 8 |
| CountryLanguagePanel | 국가/언어 선택 | store 기반 | select/apply | query/grid |
| SelectedResourceInfoPanel | 장비 상세 | selectedResource | - | selected resource |
| ControlPanel | 제어 실행 | selectedResource | submit-control | in-flight/result |
| LoadUsagePanel | 소비처 사용률 | store 기반 | - | usage status |
| PowerBalanceChart | 예측/수요 시각화 | series/store | - | safe format |
| KpiSummaryWidget | KPI 4카드 | items | - | fallback text |
| AiPerformanceWidget | 성과 게이지 | target/actual/rate | - | gauge state |

---

## 13. 품질/검증 표준

### 13.1 완료 기준(DoD)
- typecheck/build 통과
- 런타임 렌더 에러 없음 (`toFixed` 류 방어)
- 우측 패널 모드 전환 규칙 일치
- 반응형 모드(tablet/laptop/wall) 레이아웃 깨짐 없음

### 13.2 테스트 관점
- 상태 전환 단위 테스트(가능한 범위)
- 핵심 시나리오 수동검증:
  - 노드 클릭 -> selected-resource 오픈
  - 알람 ack -> 배지 변경/오류 롤백
  - 패널 닫기(X/ESC)

---

## 14. 배포/운영 연계 원칙
- 프론트 산출물은 CI 빌드 기준으로 생성
- `frontend/dist`는 Git 추적 제외
- 브랜치 정책은 `fe/* -> front` 개발 흐름을 기본으로 사용
- 운영 반영은 팀 배포 정책(Jenkins 조건) 준수

---

## 15. 구현 우선순위
1. Layout skeleton 고정
2. Topology + selection wiring
3. RightPanel 상태머신
4. 핵심 모드 3종(alarm/selected-resource/control)
5. 하단 3패널 시각화 정교화
6. 최종 반응형/접근성/성능 정리

---

## 16. 변경 이력
- v1.0: 통합 STD 초안 작성 (대시보드 설계 + 프론트 전반 규칙 통합)
