# ESS Simulator Docs

## Overview

이 폴더는 `simulator/ess-simulator` 개발 문서를 모아둔 곳이다.
현재 기준으로 `S14P31S305-205`까지 반영된 상태를 설명한다.

## Current Status

- `S14P31S305-202 ESS 명령 처리기 구현`: 완료
- `S14P31S305-203 ESS 안전 제약 및 차단 로직 구현`: 완료
- `S14P31S305-204 ESS Telemetry 주기 발행 기능 구현`: 완료
- `S14P31S305-205 ESS 시뮬레이터 테스트 코드 작성`: 완료
- 남은 작업: `206`

## Completed Notes

- 공통 command handler 구조 반영
- MQTT command → simulator command 변환 적용
- accepted / rejected ACK 반영
- interlock / expiry / comms / emergency / local safety 차단 반영
- command metadata 반영
- telemetry / heartbeat 기본 주기 `0.1초` 적용
- telemetry / heartbeat 조립 흐름을 publish cycle 함수로 분리
- publish cycle 단위 테스트 `tests/unit/test_simulator_app.py` 추가
- 명령 차단, MQTT 계약, subscriber 예외 처리 테스트 추가

## Recommended Reading Order

1. `implementation-status.md`
2. `project-structure.md`
3. `mqtt-contract-application.md`
4. `ess-state-model-application.md`
5. `ess-charge-discharge-application.md`

## Test Command

```bash
python -m unittest tests.unit.test_simulator_app tests.unit.test_safety_guards tests.unit.test_command_handler tests.unit.test_mqtt_contract tests.unit.test_state_machine tests.unit.test_calculations tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher
```

## Next Work

다음 범위는 TUI 구현이다.
