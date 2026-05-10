# 제어 명령 연동 전달 문서 (Backend 담당자용)

## 목적
- 프론트엔드는 `selected-resource` 우측 패널에서 장비별 제어 명령을 생성해 `/api/control/operator-commands`로 전송한다.
- 본 문서는 백엔드 구현팀이 필요한 계약/동작을 빠르게 확인할 수 있도록 정리한 핸드오프 문서다.

## 프론트에서 보내는 제어 요청 형식
- Endpoint: `POST /api/control/operator-commands`
- Payload

```json
{
  "site_id": "PLANT-ALPHA",
  "device_id": "ess-01",
  "resource_type": "ESS",
  "action": "START_CHARGE",
  "requested_by": "operator-01",
  "request_source": "UI",
  "request_id": "uuid-v4",
  "requested_at": "2026-05-09T12:00:00Z"
}
```

- `request_source`
  - `UI`: 운영자 직접 입력(버튼)
  - `OPTIMIZER`: 자동 최적화 엔진 발행
- `request_id`는 중복 클릭/재시도 시 멱등 처리 키로 사용 권장

## resource_type / action 매핑
- ESS
  - `START_CHARGE`, `STOP_CHARGE`, `START_DISCHARGE`, `STOP_DISCHARGE`, `STANDBY`
- DIESEL_GENERATOR (프론트 내부 타입) -> `DIESEL`로 변환 전송
  - `START_GENERATOR`, `STOP_GENERATOR`, `STANDBY`
- LOAD
  - `SHED_LOAD`, `RESTORE_LOAD`
- SWITCH
  - `OPEN_SWITCH`, `CLOSE_SWITCH`
- SOLAR
  - `SET_POWER_LIMIT`, `STANDBY`

## 백엔드 응답 계약(필수)
- 제어 성공/수락 응답은 아래 필드를 반드시 포함

```json
{
  "command_id": "uuid",
  "status": "ACCEPTED",
  "site_id": "PLANT-ALPHA",
  "target_resource_id": "ess-01",
  "action": "START_CHARGE",
  "created_at": "2026-05-09T12:00:00Z",
  "requested_by": "operator-01",
  "request_source": "UI",
  "reason_code": null,
  "reason_message": null
}
```

- `status`는 대문자 enum 유지: `ACCEPTED | REJECTED | BLOCKED | CREATED | IN_PROGRESS | RUNNING | COMPLETED | FAILED | TIMED_OUT | EXPIRED`

## 명령 이력 조회 계약
- Endpoint: `GET /api/control/commands?site_id={site_id}&limit={n}&offset={n}`
- 프론트는 이력을 우측 패널/제어 결과 표시 및 시각 상태 보정에 사용한다.
- 반드시 `target_resource_id`, `action`, `status`, `created_at`, `request_source`, `reason_code`를 포함해야 한다.

### `reason_code` 표준값(권장)
- 의도적 중지(회색): `OPERATOR_STOP`, `OPTIMIZER_STOP`, `SCHEDULED_STANDBY`
- 의도하지 않은 연결 끊김/통신 장애(빨강): `COMMUNICATION_LOSS`, `BROKER_DISCONNECTED`, `HEARTBEAT_TIMEOUT`, `LINK_DOWN`
- 정책/안전 차단(빨강): `INTERLOCK_BLOCKED`, `SAFETY_BLOCKED`, `RULE_BLOCKED`

## 프론트 시각 상태 전환 규칙 (이미 적용됨)
- 목적: 제어 명령 결과를 맵 오브젝트/선 상태에 즉시 반영
- 장비 상태
  - `FAILED`, `TIMED_OUT`, `BLOCKED`, `REJECTED` -> `error` (빨강/깜빡)
  - `STOP_*`, `OPEN_SWITCH`, `SHED_LOAD`, `STANDBY` + `reason_code in [OPERATOR_STOP, OPTIMIZER_STOP, SCHEDULED_STANDBY]` -> `stopped` (회색)
  - `START_*`, `CLOSE_SWITCH`, `RESTORE_LOAD` -> `normal` (흰색)
- 선 상태
  - `OPEN_SWITCH`, `SHED_LOAD`, `STOP_GENERATOR`, `STANDBY` -> 회색 실선
  - 실패 계열 상태 -> 빨강(깜빡)

### 통신 이상 우선 규칙 (의도하지 않은 끊김)
- 아래 중 하나 충족 시 프론트는 해당 구간/장비를 `error`(빨강/깜빡)로 우선 표시
  1. `resources` 또는 `topology` fetch 실패가 연속 3회 이상
  2. 마지막 정상 수신 후 8초 초과(stale)
- 즉, 의도적 중지(`OPERATOR_STOP`, `OPTIMIZER_STOP`)는 기본 회색이지만, 동일 시점에 통신 끊김이 감지되면 빨강이 우선된다.

## 백엔드 측 권장 보강 항목 (추가 구현 제안)
1. `GET /api/plants/{site_id}/ai/latest`
   - 현재 404 대신 문서 계약대로 503 placeholder 응답 권장
2. `/api/control/commands` 쿼리 파라미터 일관화
   - `limit/offset` 기준 유지 (프론트는 이미 해당 방식 사용)
3. 사용자 입력 제어 추적성 필드 강화
   - 이력에 `requested_by`, `request_source`, `request_id`, `reason_code`, `reason_message` 포함
   - UI 버튼 중복 클릭 시 `request_id` 기반 멱등 처리(동일 명령 중복 생성 방지)
4. 통신 장애 이벤트 표준화
   - 장비 연결 끊김 시 제어 이력/상태 이벤트에 `reason_code=COMMUNICATION_LOSS` 등 표준 코드 기록

## 테스트 체크리스트
1. ESS에서 `START_CHARGE` 전송 -> 응답 `ACCEPTED` 확인
2. `GET /api/control/commands?site_id=PLANT-ALPHA&limit=20&offset=0`에서 최신 명령 확인
3. 맵 오브젝트 상태가 제어 결과에 따라 변하는지 확인
   - 운영자/최적화 정지 명령(`reason_code=OPERATOR_STOP|OPTIMIZER_STOP`) -> 회색
   - 실패/차단/통신끊김(`FAILED|BLOCKED|COMMUNICATION_LOSS`) -> 빨강(깜빡)
4. 스위치 `OPEN_SWITCH` 후 선 상태 회색 실선 확인
5. API fetch 실패를 연속 3회 유도하거나 stale(8초+) 상황을 만들어 빨강 우선 전환 확인
