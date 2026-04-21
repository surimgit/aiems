# ESS Simulator Project Structure

## Layout

```text
ess-simulator/
├── adapters/
│   ├── inbound/
│   └── outbound/
├── config/
├── core/
├── docs/
├── tests/
├── main.py
├── mqtt_contract.py
├── runtime_config.py
└── simulator_app.py
```

## Core Responsibilities

### `core/ess.py`

- ESS 현재 상태 관리
- mode 적용
- tick 진행
- snapshot 생성
- interlock / comms / emergency 상태 반영

### `core/state_machine.py`

- 상태 enum 정의
- 상태 전이 검증
- busy / emergency / local safety 차단

### `core/policies.py`

- charge / discharge 허용 조건
- safety transition 판정

### `core/safety_guards.py`

- command expiry 검증
- interlock 검증
- comms health 검증
- emergency stop 검증
- local safety 검증

### `core/command_handler.py`

- command 처리 흐름 조립
- command type 분기
- 안전 제약 검증
- simulator 호출 위임
- ACK 생성
- reason code 정규화

## Current Command Handler Shape

- `handle_command()`: 전체 command 처리 흐름 조립
- `_dispatch_command()`: command type 분기
- `_apply_ess_mode()`: ESS mode 명령 적용
- `_ensure_mode_command_allowed()`: 안전 제약 검증
- `_apply_device_spec()`: device spec 변경 적용
- `_apply_safety_spec()`: safety spec 변경 적용
- `_build_accepted_ack()`: accepted ACK 생성
- `_build_rejected_ack()`: rejected ACK 생성
- `_normalize_reason()`: reason code 정규화

## Contract Layer

### `mqtt_contract.py`

- MQTT topic 파싱
- ESS command contract 검증
- telemetry / ack / heartbeat 모델 정의
- snapshot -> telemetry 변환

### `simulator_app.py`

- simulator, publisher, subscriber, CLI 조립
- runtime loop 실행
- `build_publish_batch()` 로 telemetry / heartbeat payload 조립
- `log_publish_batch()` 로 발행 로그 출력
- `publish_batch()` 로 MQTT publish 호출
- `run_publish_cycle()` 로 한 번의 주기 발행 사이클 수행

## Tests

현재 반영된 테스트 파일:

- `tests/unit/test_simulator_app.py`
- `tests/unit/test_safety_guards.py`
- `tests/unit/test_command_handler.py`
- `tests/unit/test_mqtt_contract.py`
- `tests/unit/test_state_machine.py`
- `tests/unit/test_calculations.py`
- `tests/unit/test_ess_state_logic.py`
- `tests/integration/test_mqtt_subscriber.py`
- `tests/integration/test_mqtt_publisher.py`
- `tests/functional/test_ess_mqtt_flow.py`

## Next Boundary

다음 범위는 테스트 코드 확대와 TUI 구현이다.
