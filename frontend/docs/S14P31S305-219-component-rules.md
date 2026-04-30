# S14P31S305-219 공통 컴포넌트 규칙

## 1. 목적
- 버튼/카드/테이블/모달/토스트 규칙을 표준화한다.

## 2. 컴포넌트 목록
- Button
- Panel Card
- Metric Card
- Status Chip
- Table
- Modal
- Toast

## 3. 규칙
- Button: Primary / Secondary / Danger
- Card: 동일 border, radius, padding 사용
- Table: 상태칩 컬럼 규칙 통일
- Modal: 파괴적 액션은 확인 단계 필수
- Toast: 우측 하단, 자동 사라짐(critical 예외 정책 별도)

## 4. 대시보드 특화
- 우측 패널은 `국가 선택` / `알람 및 최근 명령` 토글로 동작
- 단선도 노드 클릭 시 `SelectedResourcePanel` 연동

## 5. RightPanelShell 공통 구조

```txt
[Header]
- 패널 타이틀
- 보조 액션(예: 전체보기)
- 닫기(X)

[Body]
- 모드별 콘텐츠 영역

[Footer(Optional)]
- 확인/적용/전송 액션
```

## 6. 우측 패널 모드 컴포넌트

- `AlarmTopPanel` (알람 Top N)
- `RecentCommandPanel` (최근 명령 결과)
- `CountryLanguagePanel` (국가/언어 선택)
- `SelectedResourcePanel` (선택 장비 정보)
- `ControlPanel` (설비 제어)
- `LoadUsagePanel` (소비처 사용현황)

## 7. 전환 규칙

- single-active-mode: 동시에 하나의 우측 패널만 오픈
- 동일 아이콘 재클릭: 해당 패널 닫기
- 다른 아이콘 클릭: 현재 패널 닫고 대상 패널 오픈
- 노드 선택 시: `SelectedResourcePanel`을 우선 오픈 가능

## 8. DoD
- [ ] 공통 컴포넌트 명세 작성
- [ ] 상태별 예시 스크린 포함
- [ ] 우측 패널 모드별 공통 Shell 준수 확인
