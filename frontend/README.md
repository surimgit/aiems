# Frontend 구조 가이드

팀원이 `frontend` 폴더를 빠르게 이해하고, 충돌 없이 작업할 수 있도록 만든 문서입니다.

## 1) 목표

- 단일 대시보드 화면에서 여러 위젯 기능을 안정적으로 운영
- 폴더 책임을 명확히 분리해서 병렬 개발 시 충돌 최소화
- 데이터 흐름을 고정해서 유지보수 용이성 확보

## 2) 핵심 원칙

- 데이터 흐름: `API -> Store -> Feature -> Page`
- `pages`는 조립 역할만 담당 (API 직접 호출 금지)
- 도메인 규칙(예: ESS 부호)은 `domain/`에서만 관리
- 화면 크기별 차이는 페이지를 늘리지 않고 `layout preset`으로 처리

## 3) 폴더 구조와 역할

```text
frontend/
  ARCHITECTURE.md         # 전체 아키텍처 원칙
  CONVENTIONS.md          # 코딩/네이밍 규칙
  README.md               # 이 문서
  src/
    app/                  # 앱 셸, 라우터, 전역 설정
    api/                  # 백엔드 API 클라이언트
    domain/               # 도메인 규칙/변환/모델
    realtime/             # websocket/polling 소스
    stores/               # Pinia 상태관리
    features/             # 기능 단위 위젯/조합
    pages/                # 페이지 조립 레이어
    types/                # 계약 DTO + UI 타입
    ui/                   # 공통 UI primitive/pattern
```

### 현재 대시보드 기준 주요 feature

- `features/topology/`: 지도형 단선도 오버레이
- `features/detail/`: 선택 설비 상세 + 제어 패널
- `features/recommendation/`: AI 추천/승인 패널
- `features/alarm/`: 알람 요약 위젯
- `features/forecast/`: 전력 밸런스 추이
- `features/history/`: 명령 타임라인
- `features/kpi/`: KPI 요약
- `features/overview/`: 전체 조립 및 layout preset

## 4) 화면 사이즈 대응 방식

- 한 페이지(`OverviewPage.vue`)를 유지
- `features/overview/layoutPresets.ts`에서 모드별 배치 규칙만 변경
  - `tablet`
  - `laptop`
  - `wall`

즉, 페이지를 3개 만드는 것이 아니라 동일 위젯을 모드별로 재배치합니다.

## 5) 팀 작업 분담 규칙 (충돌 방지)

- `OverviewPage.vue`는 조립 담당 1명만 수정
- 기능 개발은 각자 `features/<도메인>/components/*` 중심으로 작업
- 공통 타입(`types/common.ts`)은 통합 담당자가 주기적으로 반영
- 큰 PR 1개보다 작은 PR 여러 개로 분리

## 6) 브랜치/커밋 규칙

- 브랜치: `fe/{작업유형}/{백로그이슈번호}/{기능상세}`
- 커밋 메시지: `{[백로그이슈번호]} {작업유형}:{작업메시지}`

예시:

- 브랜치: `fe/init/S14P31S305-230/front-folder-structure`
- 커밋: `[S14P31S305-230] init: 프론트엔드 폴더 구조 설계`

## 7) MR(merge request) 기본 절차

1. `frontend` 최신화
2. 작업 브랜치 분기
3. 개발/커밋/푸시
4. GitLab에서 `source: fe/... -> target: frontend` MR 생성
5. 리뷰/수정 반영 후 머지

권장 CLI 흐름:

```bash
git checkout frontend
git pull origin frontend

git checkout -b fe/{작업유형}/{백로그이슈번호}/{기능상세}

# 작업 후
git add .
git commit -m "[S14P31S305-230] init: 프론트엔드 폴더 구조 설계"
git push -u origin fe/{작업유형}/{백로그이슈번호}/{기능상세}
```

## 8) PR/MR 체크리스트

- [ ] 페이지에서 API 직접 호출 없음
- [ ] 상태/enum 표기 규칙 문서와 일치
- [ ] 위젯 책임이 feature 폴더로 분리됨
- [ ] 사이즈 모드별 레이아웃 깨짐 없음
- [ ] 불필요한 파일/주석/임시 코드 제거 완료
