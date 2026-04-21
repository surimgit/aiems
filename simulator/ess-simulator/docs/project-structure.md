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

### `core/state_machine.py`

- 상태 타입 정의
- 상태 전이 검증
- busy / emergency / local safety 차단

### `core/policies.py`

- charge / discharge 허용 여부 판단
- safety transition 판단

### `core/command_handler.py`

- command 처리 흐름 조립
- command type 분기
- simulator 적용 호출
- ACK 생성
- reason code 정규화

## 202 Command Handler Shape

`core/command_handler.py`는 현재 아래 구조를 기준으로 사용한다.

- `handle_command()`: 전체 command 처리 흐름 조립
- `_dispatch_command()`: command type 분기
- `_apply_ess_mode()`: ESS 모드 명령 적용
- `_apply_device_spec()`: device spec 변경 적용
- `_apply_safety_spec()`: safety spec 변경 적용
- `_build_accepted_ack()`: accepted ACK 생성
- `_build_rejected_ack()`: rejected ACK 생성
- `_normalize_reason()`: reason code 정규화

## Adapter Responsibilities

### `adapters/inbound/mqtt_subscriber.py`

- command topic 구독
- payload decode
- MQTT contract 검증
- command handler 호출
- rejected ACK fallback 처리

### `adapters/outbound/mqtt_publisher.py`

- telemetry publish
- ACK publish
- heartbeat publish

## Tests

현재 `202` 기준 주요 테스트 파일:

- `tests/unit/test_command_handler.py`
- `tests/unit/test_state_machine.py`
- `tests/integration/test_mqtt_subscriber.py`
- `tests/functional/test_ess_mqtt_flow.py`

## Next Boundary

`203`에서는 현재 구조를 유지한 채 safety policy와 blocking reason을 더 세분화하면 된다.
