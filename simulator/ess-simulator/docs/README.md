# ESS Simulator Docs

## Overview

이 디렉터리는 `simulator/ess-simulator` 구현 기준 문서를 모아둔 곳이다.
현재 머지 기준으로 `202`와 `203` 완료 상태가 반영되어 있다.

## Current Status

- `S14P31S305-202 ESS 명령 처리기 구현`: 완료
- `S14P31S305-203 ESS 안전 제약 및 차단 로직 구현`: 완료
- 다음 우선 작업: `204`, `205`, `206`

## Completed Notes

이번까지 반영된 핵심 내용:

- 함수 중심 `CommandHandler` 구조
- MQTT command -> simulator command 변환 경로
- accepted / rejected ACK 정리
- interlock / expiry / comms / emergency / local safety 차단
- 안전 차단 함수 분리
- command metadata 확장
- 명령 처리 및 안전 차단 테스트 추가

## Recommended Reading Order

1. `implementation-status.md`
2. `project-structure.md`
3. `mqtt-contract-application.md`
4. `ess-state-model-application.md`
5. `ess-charge-discharge-application.md`

## Test Command

```bash
python -m unittest tests.unit.test_safety_guards tests.unit.test_command_handler tests.unit.test_mqtt_contract tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher
```

## Next Work

다음 브랜치에서는 telemetry 주기 발행 보강, 테스트 확장, TUI 구현 순으로 진행하면 된다.
