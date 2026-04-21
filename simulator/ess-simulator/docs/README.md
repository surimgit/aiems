# ESS Simulator 문서 안내

## 목적

이 디렉터리는 `simulator/ess-simulator` 구현 기준 문서를 모아둔 곳이다.
외부 설계 문서를 그대로 복사하지 않고, 현재 저장소에 반영된 결과와 작업 상태를 기준으로 정리한다.

이제 이 문서는 문서 인덱스 역할만 한다.
현재 진행 상황은 `implementation-status.md` 를, 구조 설명은 `project-structure.md` 를 우선 보면 된다.

## 빠른 시작

처음 볼 때는 아래 순서로 보면 된다.

1. `implementation-status.md`
   - 지금까지 완료한 Jira 작업과 남은 작업 확인
2. `project-structure.md`
   - 현재 코드 구조와 책임 분리 확인
3. 작업별 적용 문서
   - 각 단계에서 무엇을 구현했고 어디를 수정했는지 확인

## 현재 완료 범위

현재 완료한 범위는 아래와 같다.

- 1장 기본 실행 구조
- 2장 MQTT 통신 규격 적용
- 3장 MQTT payload 모델 구현
- 4장 상태 모델 및 상태 전이 로직 구현
- 5장 ESS 충방전 및 SOC 계산 로직 구현

## 문서 분류

### 1. 공통 안내 문서

- `README.md`
  - 문서 인덱스
- `implementation-status.md`
  - 완료/진행 예정 작업 현황
- `project-structure.md`
  - 현재 디렉터리 구조와 책임 설명

### 2. 초기 구성 문서

- `basic-runtime-structure.md`
  - 기본 실행 구조 설계 및 기준
- `jira-basic-runtime-structure.md`
  - 초기 Jira 작업 정리

### 3. 작업별 적용 문서

- `mqtt-contract-application.md`
  - MQTT 계약, payload, publisher/subscriber 반영 결과
- `ess-state-model-application.md`
  - 상태 모델, 상태 전이, 안전 상태 반영 결과
- `ess-charge-discharge-application.md`
  - 충방전, 용량 기반 SOC 계산 반영 결과

## 어떤 문서를 언제 보면 되는가

| 목적 | 먼저 볼 문서 |
| --- | --- |
| 지금 어디까지 끝났는지 확인 | `implementation-status.md` |
| 현재 코드 구조 확인 | `project-structure.md` |
| MQTT 계약 반영 내용 확인 | `mqtt-contract-application.md` |
| 상태 전이 로직 확인 | `ess-state-model-application.md` |
| SOC 계산 로직 확인 | `ess-charge-discharge-application.md` |
| 초기 설계 배경 확인 | `basic-runtime-structure.md` |

## 실행 및 테스트

프로젝트 루트 `simulator/ess-simulator` 에서 실행한다.

전체 테스트:

```bash
python -m tests
```

현재까지 반영된 핵심 테스트:

```bash
python -m unittest tests.unit.test_calculations tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher tests.unit.test_mqtt_contract
```

## 다음 작업

다음 우선순위 작업은 아래와 같다.

1. ESS 명령 처리기 구현
2. ESS 안전 제약 및 차단 로직 구현
3. ESS Telemetry 주기 발행 기능 보강
4. ESS 시뮬레이터 테스트 코드 확장
5. ESS 시뮬레이터 상태 확인용 TUI 구현
