# ESS Simulator Docs

## Overview

이 디렉터리는 `simulator/ess-simulator` 구현 기준 문서를 모아둔 곳이다.
머지 후 다음 브랜치 작업을 이어가기 쉽게 현재 완료 상태와 참고 문서를 함께 정리한다.

## Current Status

- `S14P31S305-202 ESS 명령 처리기 구현`: 완료
- `S14P31S305-203 ESS 안전 제약 및 차단 로직 구현`: 아직 미완료

## 202 Completed Note

이번 브랜치에서 반영한 내용:

- 함수 중심 `CommandHandler` 구조 반영
- MQTT command -> simulator command 변환 경로 정리
- accepted / rejected ACK 정리
- 기본 reason code 정리
- 명령 처리 테스트 추가

## Recommended Reading Order

1. `implementation-status.md`
2. `project-structure.md`
3. `mqtt-contract-application.md`
4. `ess-state-model-application.md`
5. `ess-charge-discharge-application.md`

## Test Command

```bash
python -m unittest tests.unit.test_command_handler tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher
```

## Next Work

다음 브랜치에서는 `203`을 우선 진행하면 된다.
핵심은 안전 제약과 차단 로직을 명시적인 정책 함수로 확장하고 테스트를 붙이는 것이다.
