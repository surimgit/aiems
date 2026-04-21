# ESS Simulator 구현 현황

## 목적

이 문서는 ESS 시뮬레이터의 Jira 작업 진행 상태와 각 작업에 대응되는 구현 문서를 한 곳에 모아둔 현황판이다.
문서가 흩어지지 않도록, 완료 범위와 다음 작업 경계를 이 파일에서 먼저 확인하도록 한다.

## Jira 기준 진행 상태

| Jira | 작업 | 상태 | 구현/정리 문서 |
| --- | --- | --- | --- |
| `S14P31S305-200` | ESS 상태 모델 및 상태 전이 로직 구현 | 완료 | `ess-state-model-application.md` |
| `S14P31S305-201` | ESS 충방전 및 SOC 계산 로직 구현 | 완료 | `ess-charge-discharge-application.md` |
| `S14P31S305-202` | ESS 명령 처리기 구현 | 다음 작업 | - |
| `S14P31S305-203` | ESS 안전 제약 및 차단 로직 구현 | 대기 | - |
| `S14P31S305-204` | ESS Telemetry 주기 발행 기능 구현 | 부분 반영 | `mqtt-contract-application.md` |
| `S14P31S305-205` | ESS 시뮬레이터 테스트 코드 작성 | 진행 중 | `mqtt-contract-application.md`, `ess-state-model-application.md`, `ess-charge-discharge-application.md` |
| `S14P31S305-206` | ESS 시뮬레이터 상태 확인용 TUI 구현 | 대기 | - |

## 지금까지 완료한 핵심 내용

### 1. 기본 실행 구조

완료 범위:

- CLI 진입점 구성
- 런타임 설정 로딩
- simulator app 조립
- runtime loop 분리

관련 문서:

- `basic-runtime-structure.md`
- `jira-basic-runtime-structure.md`

### 2. MQTT 계약 및 입출력 경로

완료 범위:

- MQTT topic 규격 적용
- telemetry / ack / heartbeat 모델 반영
- subscriber / publisher 연결
- MQTT 계약 검증 테스트 추가

관련 문서:

- `mqtt-contract-application.md`

### 3. 상태 모델 및 상태 전이

완료 범위:

- 상태 집합 정의
- 상태 전이표 코드화
- 상태 머신 순수 함수 분리
- 안전 규칙 결과를 `SAFE_STOP`, `FAULT` 로 반영
- 상태 전이 테스트 추가

관련 문서:

- `ess-state-model-application.md`

### 4. 충방전 및 SOC 계산

완료 범위:

- `capacity_kwh` 설정 추가
- 용량 기반 SOC 계산식 반영
- 계산 함수 세분화
- SOC clamp 적용
- 계산 테스트 추가

관련 문서:

- `ess-charge-discharge-application.md`

## 현재 코드 기준 주요 포인트

- 상태 전이 규칙은 `core/state_machine.py` 에 모여 있다.
- 실제 ESS 조립 로직은 `core/ess.py` 에 있다.
- 계산 함수는 `core/calculations.py` 에 분리되어 있다.
- MQTT 계약은 `mqtt_contract.py` 에 정리되어 있다.
- 문서 인덱스는 `README.md`, 구조 설명은 `project-structure.md` 가 맡는다.

## 아직 남아 있는 작업

### 우선순위 1: 명령 처리기 확장

해야 할 일:

- 명령 종류 확장
- reason code 정리
- 상태 전이 실패/거절 응답 표준화
- 장치 스펙/안전 스펙 변경 명령 정리

### 우선순위 2: 안전 제약 및 차단 로직 고도화

해야 할 일:

- emergency stop 진입/해제 흐름
- 차단 사유 명확화
- interlock 확장
- fault / safe stop / emergency stop 차이 정교화

### 우선순위 3: 운영성 개선

해야 할 일:

- telemetry 발행 동작 보강
- 테스트 시나리오 확장
- TUI 화면 구성

## 테스트 상태

현재 핵심 검증 명령:

```bash
python -m unittest tests.unit.test_calculations tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher tests.unit.test_mqtt_contract
```

## 문서 관리 원칙

앞으로는 아래 원칙으로 유지한다.

1. 작업 현황은 `implementation-status.md` 에 먼저 반영
2. 작업 세부 내용은 작업별 `*-application.md` 문서에 반영
3. 구조 설명 변경은 `project-structure.md` 에 반영
4. 문서 추가 시 `README.md` 문서 목록도 함께 갱신
