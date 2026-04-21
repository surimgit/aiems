# ESS 시뮬레이터 프로젝트 구조

## 목적

이 문서는 `simulator/ess-simulator` 의 현재 디렉터리 구조와 각 계층의 책임을 정리한다.
구조 설명은 이 파일에 모으고, 작업별 구현 상세는 각 `*-application.md` 문서에 분리한다.

## 전체 구조

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

## 계층별 책임

### 1. 진입 계층

#### `main.py`

역할:

- CLI 인자 파싱
- 설정 파일 경로 처리
- 앱 실행 진입

#### `runtime_config.py`

역할:

- YAML 설정 로딩
- 설정값 검증
- 런타임 설정 모델 제공

현재 주요 설정:

- `plant_id`
- `device_id`
- `resource_type`
- `publish_interval_sec`
- `power_limit_kw`
- `capacity_kwh`
- `initial_soc`
- SOC 안전 임계값
- MQTT 연결 정보

### 2. 조립 계층

#### `simulator_app.py`

역할:

- 도메인 로직과 입출력 어댑터 조립
- runtime loop 실행
- telemetry / heartbeat 발행
- CLI 루프 실행

현재 `_runtime_loop()` 순서:

1. simulator tick
2. telemetry 직렬화 및 publish
3. heartbeat 직렬화 및 publish

### 3. 도메인 계층

#### `core/ess.py`

역할:

- ESS 현재 상태 보관
- 명령 적용
- tick 진행
- snapshot 생성
- 상태 머신과 계산 함수 조립

#### `core/state_machine.py`

역할:

- 상태 목록 정의
- 상태 전이표 정의
- 전이 허용 여부 검사
- 중복 명령 / busy / fault / emergency 검사

#### `core/calculations.py`

역할:

- ESS 부호 규칙 반영
- 시간 변환
- 이동 에너지량 계산
- SOC 변화율 계산
- SOC clamp

#### `core/policies.py`

역할:

- 충전 허용 여부 판단
- 방전 허용 여부 판단
- 안전 제약 위반 여부 판단

#### `core/validators.py`

역할:

- 퍼센트 범위 검증
- 양수 검증
- 임계값 순서 검증

#### `core/command_handler.py`

역할:

- 내부 command 모델 파싱
- 시뮬레이터 호출
- ACK 생성

### 4. 계약 계층

#### `mqtt_contract.py`

역할:

- MQTT topic 규격 처리
- command / telemetry / ack / heartbeat 모델 정의
- snapshot -> telemetry 변환

### 5. 입력 어댑터

#### `adapters/inbound/mqtt_subscriber.py`

역할:

- command topic subscribe
- 수신 payload 디코드
- 계약 검증
- command handler 호출
- rejected ACK 발행

#### `adapters/inbound/cli_controller.py`

역할:

- 로컬 CLI 명령 파싱
- command handler 재사용
- 디버그용 상태 조회

### 6. 출력 어댑터

#### `adapters/outbound/mqtt_publisher.py`

역할:

- telemetry publish
- ACK publish
- heartbeat publish

#### `adapters/outbound/heartbeat_publisher.py`

역할:

- heartbeat topic helper
- heartbeat payload helper

### 7. 테스트 계층

#### `tests/unit`

검증 범위:

- 상태 머신
- 계산 함수
- MQTT 계약 변환
- ESS 상태/안전 로직

#### `tests/integration`

검증 범위:

- publisher / subscriber 연결 동작

#### `tests/functional`

검증 범위:

- MQTT 명령 수신부터 ACK와 상태 반영까지 전체 흐름

## 현재 구조의 핵심 원칙

현재 코드는 아래 원칙으로 정리되어 있다.

1. 상태 전이 규칙은 `state_machine.py` 로 분리
2. 수치 계산은 `calculations.py` 로 분리
3. `ess.py` 는 도메인 조립에 집중
4. MQTT 계약은 도메인 로직과 분리
5. 테스트는 단위/통합/기능으로 나눠서 유지

## 관련 문서

- `README.md`
  - 문서 인덱스
- `implementation-status.md`
  - 작업 현황표
- `mqtt-contract-application.md`
  - MQTT 계약 반영 결과
- `ess-state-model-application.md`
  - 상태 모델 반영 결과
- `ess-charge-discharge-application.md`
  - 충방전 및 SOC 계산 반영 결과
