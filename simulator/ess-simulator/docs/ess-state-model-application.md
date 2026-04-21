# ESS 상태 모델 및 상태 전이 로직 적용

## 목적

이 문서는 ESS 시뮬레이터에 상태 모델과 상태 전이 로직을 반영한 결과를 정리한다.

대상 Jira:

- `S14P31S305-200 ESS 상태 모델 및 상태 전이 로직 구현`

기준 문서:

- 외부 설계 문서 `07-appendix/state-transitions.md`
- 외부 설계 문서 `01-System/Edge_Simulator_System.md`
- 외부 설계 문서 `09-control-policy/ess-policy.md`

## 이번 작업에서 넣은 기능

이번 작업에서는 아래 기능을 구현했다.

1. 상태 집합 정리
2. 상태 전이표 코드화
3. 명령 기반 전이 검증 분리
4. 안전 규칙 결과를 `SAFE_STOP` 또는 `FAULT`로 반영
5. 상태 머신 단위 테스트 추가

## 코드 반영 위치

### `core/state_machine.py`

상태 전이 규칙을 모아둔 순수 함수 모듈이다.

역할:

- `EssState`, `OperatingMode` 정의
- 허용 상태 전이표 정의
- 중복 명령 차단
- `IN_PROGRESS` 상태 차단
- `EMERGENCY_STOP` / `FAULT` 상태 차단
- 안전 평가 결과를 상태로 변환

핵심 함수:

- `resolve_state_for_mode()`
- `is_transition_allowed()`
- `validate_mode_transition()`
- `resolve_safety_state()`
- `sync_state_with_mode()`

### `core/ess.py`

실제 시뮬레이터가 상태 머신 함수를 조립해서 사용하는 모듈이다.

역할:

- 명령 수신 후 상태 전이 요청
- 충전/방전 정책 검사
- `IN_PROGRESS` 진입 후 최종 상태 반영
- `tick()` 기반 SOC 진행
- 안전 규칙 재평가
- snapshot 생성

## 반영한 상태 목록

현재 코드 기준 상태는 아래와 같다.

- `IDLE`
- `STANDBY`
- `CHARGING`
- `DISCHARGING`
- `IN_PROGRESS`
- `FAULT`
- `SAFE_STOP`
- `EMERGENCY_STOP`

## 반영한 전이 규칙

현재 구현 기준 핵심 전이 규칙은 아래와 같다.

| 현재 상태 | 다음 상태 | 설명 |
| --- | --- | --- |
| `STANDBY` | `CHARGING` | 충전 명령 수락 시 |
| `STANDBY` | `DISCHARGING` | 방전 명령 수락 시 |
| `CHARGING` | `DISCHARGING` | 상태 전이 허용 + 방전 조건 만족 시 |
| `DISCHARGING` | `CHARGING` | 상태 전이 허용 + 충전 조건 만족 시 |
| `ANY` | `SAFE_STOP` | 안전 임계 위반 시 |
| `ANY` | `FAULT` | 과온 등 로컬 fault 시 |
| `ANY` | `EMERGENCY_STOP` | 비상 정지 상태일 때 최우선 |

보조 규칙:

- 이미 같은 상태이면 `ALREADY_IN_STATE`
- `IN_PROGRESS` 상태에서는 `DEVICE_BUSY`
- `EMERGENCY_STOP` 상태에서는 일반 명령 차단
- `FAULT` 상태에서는 일반 명령 차단

## 명령 처리 흐름

현재 `set_mode()` 흐름은 아래와 같다.

1. `validate_mode_transition()` 호출
2. 상태 전이 가능 여부 확인
3. 충전/방전 정책 검사
4. `IN_PROGRESS` 상태 진입
5. 최종 상태와 전력값 반영

즉, 상태를 직접 덮어쓰지 않고
항상 `검증 -> 중간 상태 -> 적용` 순서로 처리한다.

## 안전 규칙 반영 방식

안전 규칙은 `tick()` 이후 매번 재평가한다.

현재 반영 기준:

- 최소 안전 SOC 이하에서 방전 지속 시 `SAFE_STOP`
- 최대 안전 SOC 이상에서 충전 지속 시 `SAFE_STOP`
- 최대 온도 초과 시 `FAULT`

강제 상태 진입 시 아래 값도 함께 정리한다.

- `operating_mode = standby`
- `target_power_kw = 0.0`
- `power_kw = 0.0`

## 테스트 반영

### `tests/unit/test_state_machine.py`

검증 범위:

- 명령 기반 목표 상태 계산
- 중복 상태 명령 거절
- `IN_PROGRESS` 차단
- `ANY -> SAFE_STOP` 허용
- 안전 평가 결과 상태 변환

### `tests/unit/test_ess_state_logic.py`

검증 범위:

- 충전 명령 후 `CHARGING` 상태 반영
- 최소 안전 SOC 진입 시 `SAFE_STOP`
- 과온 시 `FAULT`

### 실행 명령

프로젝트 루트 `simulator/ess-simulator` 에서 실행:

```bash
python -m unittest tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow
```

## 이번 작업의 범위와 다음 작업 경계

이번 문서 기준으로 완료한 범위:

- 상태 모델
- 상태 전이 검증
- 상태 전이 테스트

다음 Jira `S14P31S305-201 ESS 충방전 및 SOC 계산 로직 구현` 에서 이어서 볼 범위:

- 배터리 용량 반영 여부
- 효율 반영 여부
- SOC 계산식 고도화
- telemetry와 계산 결과 정합성 강화

## 요약

이번 작업으로 ESS 시뮬레이터는 상태를 직접 바꾸는 구조에서
상태 머신을 통해 전이를 검증하고 적용하는 구조로 바뀌었다.

이제 다음 작업에서는 이 상태 모델 위에
충방전 계산과 SOC 모델을 더 정확하게 올리면 된다.
