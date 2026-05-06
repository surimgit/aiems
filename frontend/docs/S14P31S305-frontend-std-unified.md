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
- 국가 카드 텍스트 규칙:
  - locale=ko: `KR 대한민국`
  - locale=en: `KR Korea`
- 최근 명령 설비명 표시는 임시 문자열 번역 금지, `설비 별칭(alias) -> 원본 id` 우선순위로 표시
- 선택 장비 패널의 이름 편집은 `적용(임시 저장)` 단계에서 draft만 갱신하며, 패널 하단 `변경사항 저장` 클릭 시에만 쿠키에 영구 반영

### 11.5 다국어(i18n) 및 설비 별칭 저장 규칙
- 다국어 프레임워크: `vue-i18n` (로컬 메시지 파일 `src/locales/ko.json`, `src/locales/en.json`)
- locale 영속화: `localStorage` 키 `ai-ems.locale`
- 설비 별칭 영속화: 쿠키 키 `ai-ems.resource-aliases`
  - 저장 단위: `{ [resourceId]: { ko?: string, en?: string } }`
  - 저장 시점: 사용자가 명시적으로 `변경사항 저장`을 클릭한 경우
  - 보관 정책: `max-age=315360000`(10년), `path=/`, `samesite=lax`
- 표시 우선순위:
  1) locale별 alias
  2) API `name`
  3) `resource_id`
- 한 locale에서 alias는 1개만 유지하며, 재저장 시 최신값으로 덮어쓴다.

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
- v1.1: Jira 176 반영 (하단 3패널 3열 고정, 잘림 완화, 정보 밀도 축소 규칙 확정)
- v1.2: i18n 확장 및 설비명 alias 저장 플로우 반영 (국가/알람/최근명령/KPI 문구 전환, alias draft->일괄저장 규칙, 쿠키 영속화 정책 추가)

---

## 17. 하단 3패널 반응형 표시 규칙 (정보 밀도 제어)

> 목적: 모든 모드에서 동일한 관제(wall) 밀도를 강제하지 않고, 화면 크기별로 정보 밀도를 조절해 가독성과 판단 속도를 유지한다.

### 17.1 공통 원칙
- 레이아웃 구조(`AI 예측 | KPI 요약 | AI 성과`)는 모든 모드에서 유지한다.
- 하단 패널은 `tablet/laptop/wall` 전 모드에서 3열을 유지한다.
- 카드 높이는 부모 그리드에 맞추되, 내부 콘텐츠는 고정 높이(`h-*`)보다 최소 높이(`min-h-*`)와 밀도 축소를 우선 적용한다.
- 해결 방식은 "스크롤 우선"이 아니라 "밀도 조정 우선"으로 한다.
- 모드별 차이는 **정보 양/텍스트 길이/시각 요소 수**에서만 발생하며, 컴포넌트 책임 경계는 동일해야 한다.

### 17.2 모드 정의
- `tablet`: `<= 1024px`
- `laptop`: `1025px ~ 2559px`
- `wall`: `>= 2560px`

### 17.3 1:6:2(또는 향후 조정 비율)와 하단 패널 원칙
- 상/중/하 영역은 고정 비율 강제보다 `topbar(auto) / topology(flexible) / bottom(auto)`를 우선해 잘림을 방지한다.
- 하단 영역 안에서는 3패널의 높이를 동일하게 유지한다.
- 하단 영역이 좁아지는 경우 우선순위는 다음과 같다:
  1) 보조 텍스트 축약/숨김
  2) 범례/보조지표 간소화
  3) 그래프 보조 눈금/라벨 감소
  4) (최후) 내부 스크롤 허용

---

### 17.4 위젯별 상세 규칙

#### A) `PowerBalanceChart` (AI 예측 패널)

##### tablet
- 표시: 핵심 라인(발전/소비/순전력) 유지
- 축소:
  - Y축 눈금 수 축소(최대 3~4개)
  - X축 라벨 간격 축소(예: 00/06/12/18/24)
  - 보조 설명 문구 제거
  - 범례는 한 줄 압축
- 금지:
  - 다중 보조 차트 추가
  - 긴 설명 텍스트

##### laptop
- 표시: 기본 라인 + 기본 범례 + 기본 툴팁
- 유지: 시간축 기본 라벨, 핵심 단위 표시(kW)

##### wall
- 표시: 상세 툴팁(값+단위+변화 추세), 피크 시간 강조 가능
- 허용: 보조 가이드 라인(과도하지 않은 수준)

##### 구현 메모
- 데이터가 없거나 비정상값(`undefined`, `NaN`)이면 `데이터 없음` fallback
- `toFixed`는 숫자 검증 후 호출

---

#### B) `KpiSummaryWidget` (KPI 요약 패널)

##### tablet
- 레이아웃: 2x2 유지
- 카드당 표시:
  - 라벨 1줄
  - 메인 수치 1줄
  - 보조 텍스트는 축약 또는 제거
- 아이콘 크기 축소(예: 16px)

##### laptop
- 카드 4개 모두 라벨/메인 수치/증감(핵심 1줄) 표시

##### wall
- 증감률 + 비교 기준(전월 등) + 상태 아이콘까지 표시
- 단, 텍스트 과밀 시 줄 수를 제한하고 숫자 우선

##### 구현 메모
- 카드별 수치 표현은 단위 표기 일관성 유지(kW, kWh, %)
- 긴 라벨은 `truncate` 또는 단축 라벨 사용

---

#### C) `AiPerformanceWidget` (AI 성과 패널)

##### tablet
- 게이지 반경/두께 축소
- 실적 값(핵심 수치)만 크게 유지
- 목표/달성률은 하단 1줄 요약
- 부가 문구 제거

##### laptop
- 게이지 + 목표 + 달성률 2행 구성

##### wall
- 게이지 확대 + 목표/달성률/비교 지표까지 확장 가능

##### 구현 메모
- 값 없음 상태에서는 `N/A`/`데이터 없음` 명시
- 색상 규칙(정상/경고/이상/강조색) 준수

---

### 17.5 텍스트/타이포 스케일 표준

| 요소 | tablet | laptop | wall |
|---|---|---|---|
| 패널 타이틀 | `text-base` | `text-lg` | `text-xl` |
| 메인 수치 | `text-xl` | `text-2xl` | `text-3xl` |
| 보조 라벨 | `text-xs` | `text-sm` | `text-base` |

원칙:
- 숫자 > 상태 > 설명 순으로 시각 우선순위 유지
- 줄바꿈보다 축약/요약을 우선 적용

---

### 17.6 스크롤 정책

- 기본 원칙: 내부 스크롤 의존을 최소화하고 밀도 축소로 대응
- 하단 패널은 콘텐츠 반응형 축약으로 우선 대응
- 안전장치: 화면 제약으로 잘림이 발생할 수 있는 경우 페이지 세로 스크롤을 허용한다.
- 내부 스크롤은 다음 조건에서만 허용:
  - 모드별 축약 규칙 적용 후에도 핵심 정보가 잘리는 경우
  - 로그/리스트성 콘텐츠가 본질적으로 길이 가변인 경우

---

### 17.7 수용 기준 (Acceptance)

- `tablet/laptop/wall` 3개 모드에서 하단 3패널이 구조적으로 유지된다.
- `tablet`에서도 하단 3열이 유지된다.
- `tablet`에서도 핵심 수치/상태 판독이 가능하다.
- 하단 패널 텍스트 과밀로 레이아웃 깨짐이 없다.
- 기본 정보는 밀도 축소 상태에서 우선 확인 가능해야 하며, 필요 시 최소 범위 스크롤만 동작한다.
- `typecheck/build` 통과 및 렌더 오류(`toFixed` 류) 재발 없음.

---

### 17.8 구현 체크리스트
- [x] `DashboardShell` 하단 3열 고정 및 tablet 내부 스크롤 제거
- [x] `main-area`를 `auto/flexible/auto`로 조정해 하단 잘림 완화
- [x] `PowerBalanceChart` 밀도 축소(`h-40` 제거, 패딩/타이포 축소)
- [x] `KpiSummaryWidget` 밀도 축소(카드 패딩/값 폰트/간격 축소)
- [x] `AiPerformanceWidget` 밀도 축소(`h-40` 제거, meta 세로 스택)
- [x] `typecheck/build` 통과
- [ ] tablet/laptop/wall 수동 검증 캡처 확보
