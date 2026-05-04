# S14P31S305-221 Figma 스타일 가이드 정리

## 1. 목적
- Figma 스타일 페이지를 구현 코드 규칙과 1:1로 맞춘다.

## 2. 페이지 구성
1. Color Tokens
2. Typography
3. Grid / Spacing
4. Icon Rules
5. Components
6. States
7. Dashboard Composition

## 3. Dashboard Composition 명세
- Main: Topology Stage
- Right: Selected Resource / AI Approval / Alarm + Command
- Bottom: Forecast / KPI / AI Performance
- Interaction variant:
  - Default
  - Country panel open
  - Alarm panel open
  - Node selected

## 4. Variant Matrix (필수)

| Variant ID | 화면 상태 | 트리거 | 종료 조건 |
|---|---|---|---|
| V0 | 기본(우측 닫힘) | 초기 진입 / 닫기 | 아이콘 클릭 |
| V1 | 알람 패널 오픈 | Bell 클릭 | Bell 재클릭 / 타 아이콘 클릭 |
| V2 | 최근 명령 패널 오픈 | List 클릭 | List 재클릭 / 타 아이콘 클릭 |
| V3 | 국가/언어 패널 오픈 | Globe 클릭 | Globe 재클릭 / 적용 / 타 아이콘 클릭 |
| V4 | 선택 장비 정보 오픈 | 단선도 노드 클릭 | 닫기 / 타 모드 전환 |
| V5 | 설비 제어 오픈 | 제어 진입 액션 | 닫기 / 타 모드 전환 |
| V6 | 소비처 사용현황 오픈 | 관련 아이콘/액션 | 닫기 / 타 모드 전환 |

## 5. Prototype Flow

- Top-right 아이콘은 우측 패널 모드 전환의 단일 진입점으로 사용
- 단선도 노드 선택은 `SelectedResourcePanel` 진입 트리거
- 설비 제어 진입 시 `SelectedResourcePanel -> ControlPanel` 순서를 권장

## 6. Responsive Variant Rule

- 우측 패널 오픈 시 메인 4패널은 자동 축소
- 우측 패널 닫힘 시 메인 4패널은 기준 폭으로 복귀
- 축소 상태에서도 핵심 상태/수치 가독성을 유지

## 7. 구조 와이어 포함 항목
- 폴더 트리: `frontend/src/*`
- 데이터 흐름: `API -> Store -> Feature -> Page`
- 화면 조립: `OverviewPage -> DashboardShell -> Widgets`
- 레이아웃 프리셋: `tablet/laptop/wall`

## 8. DoD
- [ ] Figma 변수/스타일/컴포넌트 페이지 완성
- [ ] 문서와 Figma 값 불일치 0건
- [ ] V0~V6 Variant 시나리오 연결 검증
