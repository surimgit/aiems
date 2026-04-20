# ESS 시뮬레이터 프로젝트 구조

## 목적

이 문서는 ESS 시뮬레이터의 디렉터리 구조와 각 영역의 책임을 정리하기 위한 기준 문서다.

ESS 시뮬레이터는 독립 실행 가능한 Edge Simulator이며, MQTT를 통해 EMS와 통신하고 ESS 상태를 시뮬레이션한다.

이 문서의 목적은 다음과 같다.

- 폴더별 책임을 명확히 한다.
- 기능 추가 위치를 일관되게 유지한다.
- 이후 작업자가 구조를 다시 해석하지 않도록 한다.

## 최상위 구조

```text
ess-simulator/
├── adapters/
├── config/
├── core/
├── docs/
├── tests/
├── tui/
├── Dockerfile
├── main.py
└── requirements.txt
```

## 실행 기준

- Python: 3.10
- Docker base image: `python:3.10-slim`
- 설정 로딩: `PyYAML`
- 설정 검증: `pydantic`
- MQTT 어댑터: `paho-mqtt`

## 디렉터리 책임

### main.py

애플리케이션 진입점이다.

책임:

- 설정 파일 로드
- 애플리케이션 구성 요소 조립
- asyncio 실행 루프 시작
- 종료 처리

`main.py`에는 비즈니스 로직을 넣지 않는다.
다만 현재 단계에서는 앱 조립을 위해 최소한의 연결 코드는 포함한다.

## config/

시뮬레이터 실행에 필요한 설정을 둔다.

예상 파일:

- `devices.yaml`: plant_id, device_id, publish interval, 초기 SOC, power limit
- `scenario.yaml`: 초기 상태나 시나리오 관련 설정

책임:

- 환경별 설정 분리
- 코드에서 하드코딩해야 할 값을 줄임

현재 설정에는 장치 스펙과 안전 스펙이 함께 들어간다.

예:

- `power_limit_kw`
- `publish_interval_sec`
- `low_soc_threshold`
- `high_soc_threshold`
- `min_safe_soc_threshold`
- `max_safe_soc_threshold`
- `mqtt_broker_host`
- `mqtt_broker_port`

## core/

ESS 시뮬레이터의 핵심 로직을 둔다.

예상 파일:

- `ess.py`: ESS 상태와 충방전 계산
- `state_machine.py`: 상태 전이 규칙
- `command_handler.py`: command 해석과 적용 판단
- `scenario.py`: 시뮬레이션 입력 조건 처리

책임:

- 순수 도메인 로직
- MQTT나 UI에 의존하지 않는 계산과 판단

원칙:

- `core/` 안에서는 외부 브로커 세부사항을 몰라야 한다.
- 입력값을 받아 상태를 계산하고 결과를 반환하는 구조를 유지한다.

현재는 `ess.py`에서 아래 책임을 가진다.

- 현재 SOC, power, mode, state 관리
- device spec 변경
- safety spec 변경
- tick 단위 충방전 반영
- safety rule 적용

## adapters/

외부 시스템과의 입출력을 담당한다.

구조:

```text
adapters/
├── inbound/
└── outbound/
```

### adapters/inbound/

외부에서 들어오는 입력을 처리한다.

예상 파일:

- `mqtt_subscriber.py`: EMS command subscribe

책임:

- MQTT command 수신
- 수신 payload 파싱
- core 로직 호출

현재는 MQTT command와 로컬 CLI command가 모두 같은 `CommandHandler`를 사용한다.

### adapters/outbound/

외부로 나가는 메시지를 처리한다.

예상 파일:

- `mqtt_publisher.py`: telemetry, ack publish
- `heartbeat_publisher.py`: heartbeat publish

책임:

- MQTT topic 생성
- payload 직렬화
- publish 처리

## tui/

로컬에서 시뮬레이터 상태를 확인하기 위한 UI를 둔다.

예상 파일:

- `app.py`
- `widgets/device_panel.py`
- `widgets/control_panel.py`
- `widgets/command_log.py`

책임:

- 현재 SOC, mode, power, state 표시
- 최근 command / ack 로그 표시

원칙:

- TUI는 상태를 보여주는 계층이다.
- 실제 상태 계산 로직은 `core/`에 둔다.

## tests/

핵심 로직 검증을 위한 테스트를 둔다.

예상 파일:

- `test_ess.py`
- `test_state_machine.py`
- `test_command_handler.py`

책임:

- 충방전 계산 검증
- 상태 전이 검증
- 명령 처리 검증
- 예외 상황 검증

## docs/

작업 기준과 지라 정리를 위한 문서를 둔다.

예상 파일:

- `README.md`
- `basic-runtime-structure.md`
- `jira-basic-runtime-structure.md`
- `project-structure.md`
- `mqtt-contract-application.md`

책임:

- 작업 기준 정리
- 프로젝트 구조 설명
- 지라 기준 기록

## 실행 흐름

ESS 시뮬레이터의 기본 흐름은 아래와 같다.

1. `main.py` 시작
2. `config/` 설정 로드
3. MQTT subscriber / publisher 구성
4. 메인 루프 시작
5. `core/ess.py`가 tick마다 상태 계산
6. `adapters/outbound/`가 telemetry 발행
7. command 수신 시 `adapters/inbound/`가 `core/command_handler.py` 호출
8. 처리 결과를 ACK 또는 상태 변경으로 반영
9. 로컬 CLI 명령도 같은 handler를 통해 동일하게 반영

## 설계 원칙

### 1. 독립성 유지

ESS 시뮬레이터는 다른 자원 시뮬레이터와 코드 공유 없이 독립 개발 가능해야 한다.

### 2. 문서 기준 우선

MQTT topic과 payload는 설계 문서 기준을 우선한다.

### 3. 로직과 입출력 분리

ESS 계산 로직은 `core/`, 통신은 `adapters/`에 둔다.

### 4. 점진적 구현

초기에는 실행 구조를 먼저 만들고, 이후 MQTT, payload, 상태 전이, 충방전 로직 순으로 확장한다.

## 이후 작업 연결

현재 구조 문서 이후 권장 작업 순서는 다음과 같다.

1. 기본 실행 구조 구성
2. MQTT 통신 규격 적용
3. MQTT payload 모델 구현
4. ESS 충방전 및 SOC 계산 로직 구현
5. ESS 상태 전이 로직 구현
6. ESS 명령 처리기 구현
7. 테스트 작성
8. TUI 구현

## 현재 단계

현재 프로젝트는 `1. 기본 실행 구조 구성` 단계까지 완료된 상태다.

다음 작업은 아래 순서로 이어간다.

1. MQTT topic / payload 규격 정합성 점검
2. EMS command / ACK 형식 고정
3. telemetry payload 필드 정리
4. 지라 2번 작업 진행

## 상태 업데이트

현재 코드 기준으로는 `2. MQTT 통신 규격 적용`까지 반영되었다.

추가된 주요 포인트:

- `mqtt_contract.py`로 MQTT 계약 모델 분리
- `tests/unit`, `tests/integration`, `tests/functional` 구조 추가
- `python -m tests`로 전체 테스트 실행 가능
