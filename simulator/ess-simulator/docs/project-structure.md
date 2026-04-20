# ESS 시뮬레이터 프로젝트 구조

## 목적

이 문서는 ESS 시뮬레이터의 디렉터리 구조와 각 영역의 책임을 현재 코드 기준으로 정리한다.

## 디렉터리 개요

```text
ess-simulator/
├─ adapters/
│  ├─ inbound/
│  └─ outbound/
├─ config/
├─ core/
├─ docs/
├─ tests/
├─ tui/
├─ main.py
├─ mqtt_contract.py
├─ runtime_config.py
└─ simulator_app.py
```

## 런타임 진입점

### `main.py`

역할:

- CLI 인자 파싱
- 설정 파일 로딩
- 앱 실행 진입

### `runtime_config.py`

역할:

- YAML 설정 로딩
- 필수 값 검증
- 런타임 설정 모델 제공

## 앱 조립 계층

### `simulator_app.py`

역할:

- 도메인 로직과 MQTT 어댑터 조립
- runtime loop 실행
- telemetry / heartbeat 주기 발행
- CLI 루프 실행

현재 기준으로 `_runtime_loop()` 에서 아래 순서가 수행된다.

1. simulator tick
2. telemetry 직렬화 및 publish
3. heartbeat 직렬화 및 publish

## 도메인 계층

### `core/`

도메인 규칙과 시뮬레이터 상태 계산을 담당한다.

주요 파일:

- `ess.py`
  - ESS 상태, spec, tick, snapshot
- `calculations.py`
  - 전력, SOC, 에너지 계산 함수
- `policies.py`
  - 충방전 허용 여부, 안전 제약 판단
- `validators.py`
  - 입력값 검증
- `command_handler.py`
  - 내부 command 적용과 ACK 결과 생성

원칙:

- MQTT, CLI, UI를 모른다
- 순수 계산과 상태 전이만 담당한다

## 계약 계층

### `mqtt_contract.py`

브로커와 주고받는 MQTT 계약을 한 곳에 모아둔 파일이다.

포함 내용:

- 일반 topic builder / parser
- heartbeat topic builder / parser
- ESS command 모델
- telemetry 모델
- ACK 모델
- heartbeat 모델
- snapshot -> telemetry 변환

현재 모델은 `extra="forbid"` 를 사용해 문서에 없는 필드를 거부한다.

## 입구 어댑터

### `adapters/inbound/mqtt_subscriber.py`

역할:

- command topic subscribe
- 수신 payload 디코딩
- 계약 검증
- 내부 command handler 호출
- rejected ACK 생성

### `adapters/inbound/cli_controller.py`

역할:

- 로컬 CLI 명령 파싱
- 내부 command handler 재사용
- 디버그용 상태 조회 지원

## 출구 어댑터

### `adapters/outbound/mqtt_publisher.py`

역할:

- telemetry publish
- ACK publish
- heartbeat publish

### `adapters/outbound/heartbeat_publisher.py`

역할:

- heartbeat topic helper
- heartbeat payload helper

## 설정

### `config/`

주요 설정:

- `plant_id`
- `device_id`
- `resource_type`
- `publish_interval_sec`
- `power_limit_kw`
- `low_soc_threshold`
- `high_soc_threshold`
- `min_safe_soc_threshold`
- `max_safe_soc_threshold`
- `mqtt_broker_host`
- `mqtt_broker_port`

## 테스트

### `tests/`

테스트는 3단계로 나뉜다.

- `unit`
  - topic / payload / mapper 검증
- `integration`
  - publisher / subscriber 동작 검증
- `functional`
  - 수신 명령에서 ACK와 상태 반영까지 검증

실행:

```bash
python -m tests
```

## 문서

### `docs/`

레포 내부 구현 기준 문서를 유지한다.

- `README.md`
  - 현재 구현 상태 요약
- `basic-runtime-structure.md`
  - 1장 기준 정리
- `jira-basic-runtime-structure.md`
  - 1장 지라 정리
- `project-structure.md`
  - 현재 구조 설명
- `mqtt-contract-application.md`
  - MQTT 계약 반영 결과
