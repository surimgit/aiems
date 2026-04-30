# ESS Simulator Implementation Status

## Summary

이 문서는 `simulator/ess-simulator` 작업 상태를 Jira 기준으로 정리한다.
현재 기준으로 `S14P31S305-205` 및 topology wire_fault 연동까지 구현과 테스트 반영이 끝난 상태다.

## Jira Status

| Jira             | 설명                        | 상태   | 메모                                                   |
|------------------|---------------------------|------|------------------------------------------------------|
| `S14P31S305-200` | ESS 상태 모델 및 상태 전이 로직 구현   | 완료   | 기존 반영                                                |
| `S14P31S305-201` | ESS 충방전 및 SOC 계산 로직 구현    | 완료   | 기존 반영                                                |
| `S14P31S305-202` | ESS 명령 처리기 구현             | 완료   | 기존 반영                                                |
| `S14P31S305-203` | ESS 안전 제약 및 차단 로직 구현      | 완료   | 기존 반영                                                |
| `S14P31S305-204` | ESS Telemetry 주기 발행 기능 구현 | 완료   | 기본 주기 0.1초, publish cycle 함수 분리                      |
| `S14P31S305-205` | ESS 시뮬레이터 테스트 코드 작성       | 완료   | 계산, 안전, MQTT 계약, subscriber 예외, publish cycle 테스트 확장 |
| `S14P31S305-49`  | Topology wire_fault 연동     | 완료   | topology 서비스 구독, SOC 고정, comms_health=wire_fault 발행  |
| `S14P31S305-206` | ESS 시뮬레이터 상태 확인용 TUI 구현   | 진행 전 | 미착수                                                  |

## 202 Done

- MQTT command contract 기준 command payload 검증 반영
- `core/command_handler.py` 중심의 처리 흐름 분리
- accepted / rejected ACK 생성 반영
- 명령 처리 테스트 보강

## 203 Done

- `core/safety_guards.py` 반영
- interlock 차단 반영
- command expiry 차단 반영
- comms failure 차단 반영
- emergency stop 차단 반영
- local safety / local fault 차단 반영
- reason code 포함 rejected ACK 반영
- `EssStatus`에 `interlock_active`, `comms_healthy` 상태 반영
- command metadata `issued_at`, `expires_in_sec`, `force`, `source` 반영

## 204 Done

- `config/devices.yaml` 기본 `publish_interval_sec`를 `0.1`로 조정
- `simulator_app.py`에서 주기 발행 흐름을 `build_publish_batch()`, `log_publish_batch()`, `publish_batch()`, `run_publish_cycle()`로 분리
- telemetry 와 heartbeat 조립, 로그 출력, 발행 단계를 각각 함수로 분리해 테스트하기 쉽게 구성
- `tests/unit/test_simulator_app.py` 추가로 broker 없이도 한 번의 publish cycle을 검증 가능하게 보강
- `tests/unit/test_calculations.py`, `tests/unit/test_ess_state_logic.py`에 0.1초 기준 계산 검증 추가

## 205 Done

- `tests/unit/test_command_handler.py`
  - `EMERGENCY_STOP_ACTIVE` 거부 테스트 추가
  - `update_safety_spec` 적용 테스트 추가
- `tests/unit/test_mqtt_contract.py`
  - 충전 시 `P < 0` 직렬화 검증
  - 전류 절대값 계산 검증
  - 다른 device 대상 command 거부 검증
- `tests/integration/test_mqtt_subscriber.py`
  - 깨진 JSON payload가 `unknown` command_id의 rejected ACK로 처리되는지 검증
- `tests/unit/test_simulator_app.py`
  - publish cycle 연속 실행 시 tick/publish 호출 누적 검증 추가
- 계산, 안전, MQTT 계약, subscriber 예외 처리, publish cycle 반복성을 테스트로 고정

## Verification

```bash
python -m unittest tests.unit.test_simulator_app tests.unit.test_safety_guards tests.unit.test_command_handler tests.unit.test_mqtt_contract tests.unit.test_state_machine tests.unit.test_calculations tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher
```

## S14P31S305-49 Done (Topology wire_fault 연동)

- `simulator_app.py`에 `_topology_line_states`, `_topology_switch_states` 모듈 레벨 딕셔너리 추가
- `_is_wire_fault(device_id)` 함수로 `affected_devices` 기준 장애 판단
- `MqttCommandSubscriber`에서 `{plant_id}/topology/#` 구독 및 `topology_callback` 처리
- wire_fault 진입 시 `power_kw=0.0`, SOC는 진입 시점 값으로 고정 (`_frozen_soc`)
- wire_fault 해제 시 frozen SOC 해제, 정상 계산 재개
- telemetry `comms_health` 필드: `"wire_fault"` / `"ok"` 분기 발행
- 통합 테스트: `tests/test_02_ess_soc_freeze.py` (시나리오 4)

## Next Boundary

다음 작업 범위는 `S14P31S305-206`이다.
