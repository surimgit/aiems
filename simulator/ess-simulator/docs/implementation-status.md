# ESS Simulator Implementation Status

## Summary

이 문서는 `simulator/ess-simulator` 작업 상태를 Jira 기준으로 정리한다.
현재 기준으로 `S14P31S305-202 ESS 명령 처리기 구현`은 완료 처리한다.

## Jira Status

| Jira | 작업 | 상태 | 비고 |
| --- | --- | --- | --- |
| `S14P31S305-200` | ESS 상태 모델 및 상태 전이 로직 구현 | 완료 | 기존 반영 |
| `S14P31S305-201` | ESS 충방전 및 SOC 계산 로직 구현 | 완료 | 기존 반영 |
| `S14P31S305-202` | ESS 명령 처리기 구현 | 완료 | 이번 브랜치 반영 |
| `S14P31S305-203` | ESS 안전 제약 및 차단 로직 구현 | 진행 전 | 다음 브랜치 작업 |
| `S14P31S305-204` | ESS Telemetry 주기 발행 기능 구현 | 진행 중 | 기존 MQTT 문서 기준 일부 반영 |
| `S14P31S305-205` | ESS 시뮬레이터 테스트 코드 작성 | 진행 중 | 일부 테스트 존재, 추가 확장 필요 |
| `S14P31S305-206` | ESS 시뮬레이터 상태 확인용 TUI 구현 | 진행 전 | 미구현 |

## 202 Done

반영 범위:

- MQTT command contract 검증 후 내부 command 모델로 변환하는 흐름 정리
- `core/command_handler.py`를 함수 중심 구조로 분리
- `handle_command()`는 조립만 담당하고 세부 처리는 개별 함수로 분리
- accepted / rejected ACK 생성 경로 정리
- 기본 reason code를 문서 기준으로 정리
- 명령 처리 단위 테스트 추가

주요 반영 파일:

- `core/command_handler.py`
- `core/state_machine.py`
- `core/policies.py`
- `adapters/inbound/mqtt_subscriber.py`
- `tests/unit/test_command_handler.py`
- `tests/unit/test_state_machine.py`
- `tests/integration/test_mqtt_subscriber.py`
- `tests/functional/test_ess_mqtt_flow.py`

## Verification

```bash
python -m unittest tests.unit.test_command_handler tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher
```

## Boundary

이번 브랜치에서는 `202`만 완료로 본다.

다음 브랜치에서 다룰 `203` 범위:

- interlock 기반 차단
- command expiry 차단
- comms failure 기반 차단
- emergency/local safety 차단 정책 세분화
- safety reason code와 테스트 확장
