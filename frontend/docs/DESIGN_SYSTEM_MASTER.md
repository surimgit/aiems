# EMS Design System Master

## 문서 목적
- 관제 대시보드 UI/UX 구현 전, 디자인 규칙을 MD 기준으로 고정한다.
- Jira 이슈 `S14P31S305-215` ~ `S14P31S305-221` 산출물을 연결한다.

## 적용 범위
- 대상 화면: `OverviewPage` 기반 단일 대시보드
- 레이아웃 모드: `tablet`, `laptop`, `wall`
- 기술 스택: Vue3 + TypeScript + Tailwind + Pinia

## 구조 원칙
- 데이터 흐름: `API -> Store -> Feature -> Page`
- 페이지는 조합 전용, API 직접 호출 금지
- 상태/알람/명령 표기는 문서 규칙과 1:1 매핑

## 문서 인덱스
1. [S14P31S305-215-color-system.md](./S14P31S305-215-color-system.md)
2. [S14P31S305-216-typography.md](./S14P31S305-216-typography.md)
3. [S14P31S305-217-spacing-grid.md](./S14P31S305-217-spacing-grid.md)
4. [S14P31S305-218-icon-rules.md](./S14P31S305-218-icon-rules.md)
5. [S14P31S305-219-component-rules.md](./S14P31S305-219-component-rules.md)
6. [S14P31S305-220-state-rules.md](./S14P31S305-220-state-rules.md)
7. [S14P31S305-221-figma-style-guide.md](./S14P31S305-221-figma-style-guide.md)

## 운영 메모
- 지도 공급자: Google Maps JavaScript API 통일(국내/해외 공통)
- 국가 선택 시 단선도/데이터 전환 동작을 동일 규칙으로 적용

## 대시보드 Variant 인덱스 (구현 전 고정)

- `V0`: 기본 화면 (우측 패널 닫힘)
- `V1`: 알람 패널 오픈 (Top 3)
- `V2`: 최근 명령 결과 패널 오픈
- `V3`: 국가/언어 패널 오픈
- `V4`: 선택 장비 정보 패널 오픈
- `V5`: 설비 제어 패널 오픈
- `V6`: 소비처 사용현황 패널 오픈

> 원칙: 우측 패널은 동시에 1개만 오픈한다. (single-active-mode)

## 문서 역할 매핑 (Single Source of Truth)

- 상태머신/전이 규칙: `S14P31S305-220-state-rules.md`
- 우측 패널/공통 컴포넌트 구조: `S14P31S305-219-component-rules.md`
- 반응형 축소/확장 계약: `S14P31S305-217-spacing-grid.md`
- 아이콘 트리거/배지 규칙: `S14P31S305-218-icon-rules.md`
- Figma Variant/프로토타입 흐름: `S14P31S305-221-figma-style-guide.md`

## 완료 기준 (Master)
- [ ] 215~221 문서가 모두 작성됨
- [ ] 토큰/상태/컴포넌트 규칙이 상호 모순 없음
- [ ] Figma 스타일 페이지와 문서가 동일한 값을 사용함
