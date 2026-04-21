# ESS Simulator Project Structure

## Layout

```text
ess-simulator/
├─ adapters/
│  ├─ inbound/
│  └─ outbound/
├─ config/
├─ core/
├─ docs/
├─ tests/
├─ main.py
├─ mqtt_contract.py
├─ runtime_config.py
└─ simulator_app.py
```

## Core Responsibilities

### `core/ess.py`

- ESS 현재 상태 보관
- mode 적용
- tick 처리
- snapshot 반환
- interlock / comms / emergency 상태 보관

### `core/state_machine.py`

- 상태 타입 정의
- 상태 전이 검증
- busy / emergency / local safety 차단

### `core/policies.py`

- charge / discharge 허용 여부 판단
- safety transition 판단

### `core/safety_guards.py`

- command expiry 검사
- interlock 검사
- comms health 검사
- emergency stop 검사
- local safety 검사

### `core/command_handler.py`

- command 처리 흐름 조립
- command type 분기
- 안전 차단 함수 호출
- simulator 적용 호출
- ACK 생성
- reason code 정규화

## Current Command Handler Shape

- `handle_command()`: 전체 command 처리 흐름 조립
- `_dispatch_command()`: command type 분기
- `_apply_ess_mode()`: ESS 모드 명령 적용
- `_ensure_mode_command_allowed()`: 안전 차단 조건 검사
- `_apply_device_spec()`: device spec 변경 적용
- `_apply_safety_spec()`: safety spec 변경 적용
- `_build_accepted_ack()`: accepted ACK 생성
- `_build_rejected_ack()`: rejected ACK 생성
- `_normalize_reason()`: reason code 정규화

## Contract Layer

### `mqtt_contract.py`

- MQTT topic 파싱
- ESS command contract 검증
- optional command metadata 허용
- telemetry / ack / heartbeat 모델 정의

## Tests

현재 주요 테스트 파일:

- `tests/unit/test_safety_guards.py`
- `tests/unit/test_command_handler.py`
- `tests/unit/test_mqtt_contract.py`
- `tests/unit/test_state_machine.py`
- `tests/integration/test_mqtt_subscriber.py`
- `tests/functional/test_ess_mqtt_flow.py`

## Next Boundary

다음 단계는 telemetry 발행 보강, 테스트 시나리오 확장, TUI 구현이다.
