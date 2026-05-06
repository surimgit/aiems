# S14P31S305-358 STD (Software Technical Design)

## 1. 문서 목적
- 16:9 산업용 관제형 AI EMS 메인 대시보드의 UI/UX 설계를 구현 가능한 기술 명세로 고정한다.
- `OverviewPage` 단일 화면 기준으로 레이아웃, 패널 전환, 컴포넌트 책임, 상태 규칙을 정의한다.

## 2. 범위
- 대상: `frontend/src/pages/OverviewPage.vue`
- 핵심 Feature:
  - `features/topology`
  - `features/overview` (Right Panel 포함)
  - `features/forecast`
  - `features/kpi`
  - `features/recommendation`
- 비범위(후속): History 고도화, polling 경쟁 상태 최적화

## 3. 디자인 핵심 원칙
- SCADA 관제형: 정보 과밀보다 상태 판단 속도를 우선한다.
- 색상은 제한적으로 사용한다.
  - 정상 `#22C55E`, 경고 `#F59E0B`, 이상 `#EF4444`, 강조 `#3B82F6`
- 상단 KPI 카드 금지, 텍스트 최소화, 숫자/상태 중심 표시
- 단일 화면 + 모드 전환(우측 패널) 구조 유지

## 4. 16:9 레이아웃 설계

### 4.1 전체 구조
```txt
[Header]
  좌: 로고/서비스명
  우: 아이콘 4개 + 시계/실시간 상태

[Main Topology Area + Right Panel Area]
  좌: Topology Stage (최대 영역)
  우: Right Panel (기본 닫힘)

[Bottom Feature Area]
  3열 고정: AI 예측 | KPI 요약 | AI 성과
```

### 4.2 간격/여백
- 외곽 패딩: 32px 이상
- 패널 간격: 20~24px
- 카드 radius: 12~16px
- 테두리: `rgba(255,255,255,0.1)`

### 4.3 반응형 모드
- `tablet`: 우측 패널 오버레이
- `laptop`: 우측 패널 사이드 배치(메인 축소)
- `wall`: 우측 패널 확장 폭 + 하단 패널 동일 높이 유지

### 4.4 176 반영 레이아웃 정책
- 하단 3패널은 `tablet/laptop/wall` 전 모드에서 **항상 3열 유지**한다.
- `main-area`는 고정 비율 강제보다 `topbar(auto) / topology(flexible) / bottom(auto)`를 우선한다.
- 하단 잘림 대응은 내부 스크롤보다 **정보 밀도 축소(패딩/타이포/보조정보)**를 우선 적용한다.

## 5. 상단 Header 설계

### 5.1 요소 구성
- 로고 텍스트: `AI EMS Dashboard`
- 서브타이틀: `Energy Management System`
- 아이콘 4종:
  - 알림(🔔)
  - 최근 명령(📄)
  - 국가 선택(🌍)
  - 설정(⚙️)
- 우측 시간/실시간 배지 표시

### 5.2 상호작용 규칙
- active 아이콘: 파란 아웃라인 표시
- 동일 아이콘 재클릭: 패널 닫힘
- 다른 아이콘 클릭: 해당 모드로 전환

## 6. Topology 설계

### 6.1 표현 대상
- 태양광, ESS, 스위치, 메인버스, 디젤발전기, Load Center
- 노드: `TopologyNode`
- 연결선: `TopologyFlowLine`

### 6.2 상태 표현
- 텍스트 최소화, 상태점/테두리/강조색으로 우선 표현
- 범례와 실제 선 스타일 1:1 매칭

### 6.3 인터랙션
- 노드 클릭 시 항상 `selected-resource` 패널 자동 오픈
- 패널 열림 상태에서도 토폴로지 클릭 허용

## 7. Right Panel 상태머신/모드 규칙

### 7.1 기본 정책
- 기본 상태: 닫힘
- 닫기 수단: `X` 버튼 + `ESC`
- 패널 오픈 애니메이션: 180ms

### 7.2 모드 목록
- `alarm`
- `recent-command`
- `country-language`
- `selected-resource`
- `control`
- `load-usage`

### 7.3 헤더 타이틀 규칙
- `모드명 + 컨텍스트`
- 예: `설비 제어 · 선택 장비: ESS-01`

### 7.4 모드별 상세 규칙
- Alarm Top 3: 심각도 우선 + 최신순
- Alarm ack 후: 목록 유지 + `확인됨` 배지
- 최근 명령 결과: 기본 8개
- 최근 명령 결과 색상: 실패만 빨강 강조(나머지 중성)
- 국가선택: 검색창 항상 노출
  - tablet 8개(2x4)
  - laptop 12개(3x4)
  - wall 20개(4x5)

## 8. 하단 3패널 설계
- 구성: `AI 예측` | `KPI 요약` | `AI 성과`
- 규칙: 3패널 동일 높이 고정
- 그래프 과다 금지(패널당 핵심 시각화 1개)
- 구현 원칙:
  - 위젯 내부 `h-*` 고정 높이보다 `min-h-*` 중심으로 구성해 압축/확장을 허용한다.
  - 텍스트 과밀 시 `숫자 > 상태 > 설명` 우선순위로 축약한다.
  - `tablet`에서는 보조 정보 줄 수를 줄이고 핵심 수치 판독을 우선한다.

## 9. 컴포넌트 구조 설계표 (Props / Events / State)

| 컴포넌트 | 책임 | 주요 Props | 주요 Events | 내부/연결 State |
|---|---|---|---|---|
| `OverviewPage` | 화면 오케스트레이션 | 없음(상위 page) | 없음 | `mode`, `rightPanelState`, `viewportWidth` |
| `TopBarKpiStrip` | 헤더 아이콘/상태 표시 | `powerSummary`, `activeAlarmCount` | `toggle-mode(mode)` | active icon id |
| `DashboardShell` | 3구역 레이아웃 | `mode`, `panelOpen` | 없음 | 레이아웃 클래스 상태 |
| `TopologyStage` | 단선도 컨테이너 | `topology` | `select-node(nodeId)` | 선택 대상 node id |
| `TopologyNodeLayer` | 설비 노드 렌더 | `nodes` | `select-node(nodeId)` | node highlight |
| `TopologyLineLayer` | 연결선 렌더 | `lines` | 없음 | flow/comm style |
| `RightPanelShell` | 우측 패널 공통 shell | `title` | `close` | open/close transition |
| `AlarmTopPanel` | Top3 알람 표시 | (store 기반) | `ack(alarmId)` | severity sort, ack state |
| `RecentCommandPanel` | 최근 명령 이력 | (store 기반) | `view-all` | list(8), fail highlight |
| `CountryLanguagePanel` | 국가/언어 선택 | (store 기반) | `select-country`, `select-lang`, `apply` | search query, responsive grid |
| `SelectedResourceInfoPanel` | 선택 장비 상세 | `selectedResource`(또는 store) | 없음 | selected resource snapshot |
| `ControlPanel` | 장비 제어 액션 | `selectedResource`(또는 store) | `submit-control` | command in-flight/status |
| `LoadUsagePanel` | 소비처별 사용 현황 | (store 기반) | 없음 | usage percent + 상태 |
| `PowerBalanceChart` | 수요/발전 예측 | `series`(or store) | timeframe 변경(선택) | safe numeric format |
| `KpiSummaryWidget` | KPI 4카드 표시 | `items` | 없음 | fallback text |
| `AiPerformanceWidget` | 게이지 달성률 표시 | `target`, `actual`, `rate` | 없음 | gauge range state |

## 10. 데이터 흐름
```txt
API Client -> Pinia Store -> Feature Composable -> OverviewPage -> UI Component
```

원칙:
- 페이지에서 API 직접 호출 금지
- Feature는 UI 조합/가공 책임
- Store는 계약/상태/액션 책임

## 11. 오류/예외 처리 규칙
- 숫자 렌더링 시 `toFixed` 직호출 금지, 숫자 가드 후 포맷
- 데이터 없음 상태는 공통 fallback (`데이터 없음`) 사용
- 패널 API 액션 실패 시 토스트/상태 배지로 사용자 피드백

## 12. 검증 기준 (DoD)
- `typecheck` / `build` 통과
- 16:9 기준 레이아웃 깨짐 없음
- 우측 패널 모드 전환/닫기 규칙 일치
- 노드 클릭 -> selected-resource 자동 오픈 동작
- 하단 3패널 동일 높이 유지
- `tablet`에서도 하단 3열 구조 유지
- 하단 패널 텍스트 과밀로 인한 잘림/깨짐 없음
- 상태 색상 규칙 위반 없음

## 14. 변경 이력
- v1.0: 초기 STD 작성
- v1.1: Jira 176 반영 (하단 3열 고정, 잘림 완화, 밀도 축소 우선 정책)

## 13. 구현 우선순위
1. Layout skeleton (`Header`, `Shell`, `Bottom 3-grid`)
2. Topology stage + node selection wiring
3. RightPanelShell + mode switch state machine
4. 우선 모드 3종(`alarm`, `selected-resource`, `control`) 완성
5. 나머지 모드/차트/미세 인터랙션 확장
