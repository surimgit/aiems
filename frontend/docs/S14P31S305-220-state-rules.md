# S14P31S305-220 상태 규칙 정의

## 1. 목적
- 운영 상태, 알람 상태, 명령 상태를 명확히 분리/정의한다.

## 2. 알람 상태
- Severity: `INFO`, `WARNING`, `HIGH`, `CRITICAL`
- 표시 원칙: 색 + 텍스트 + 아이콘 병기

## 3. 명령 상태
- `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `BLOCKED`, `EXECUTED`

## 4. 화면 상태
- `loading`: 스켈레톤 또는 로더
- `error`: 에러 코드 + 재시도
- `empty`: 데이터 없음 안내

## 5. 알람 UX 규칙
- 새 알람은 우측 하단 토스트로 표시
- 일반 알람은 N초 후 자동 닫힘
- 아이콘 배지 숫자 누적
- 알림 패널 오픈 시 읽음 처리 정책 적용

## 6. 우측 패널 상태머신

```txt
closed
  -> opening
  -> open(mode)
  -> switching(modeA -> modeB)
  -> closing
  -> closed
```

- `mode`: alarm / recent-command / country-language / selected-resource / control / load-usage
- 동시에 1개 mode만 활성화한다.

## 7. 모드별 fallback 상태

- Alarm Panel: `empty`(알람 없음), `error`(조회 실패)
- Recent Command Panel: `empty`(이력 없음), `error`, `stale`(지연)
- Country/Language Panel: `empty`(검색 결과 없음), `error`
- Selected Resource Panel: `empty`(선택 장비 없음), `error`
- Control Panel: `error`(전송 실패), `pending-timeout`(응답 지연)
- Load Usage Panel: `empty`(집계 데이터 없음), `error`

## 8. 실시간 데이터 상태

- `fresh`: 최신 수신
- `stale`: 마지막 업데이트 임계시간 초과
- `disconnected`: 실시간 채널 단절

> stale/disconnected 시 색상 + 텍스트 + 타임스탬프를 함께 노출한다.

## 9. DoD
- [ ] 상태 매핑표 완성
- [ ] 알람/명령/화면상태 컴포넌트 시나리오 검증
- [ ] 우측 패널 상태머신 전이 시나리오 검증
