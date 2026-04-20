# ESS 시뮬레이터 기본 실행 구조

## 목적

ESS 시뮬레이터가 로컬과 Docker 환경에서 일관되게 실행될 수 있도록 최소 실행 구조를 만든다.

이 작업은 기능 구현보다 먼저 아래 4가지를 안정적으로 고정하는 데 목적이 있다.

- 진입점
- 설정 로딩
- 실행 루프
- 기본 디렉터리 책임 분리

## 범위

이번 작업에서 포함하는 항목:

- Python 3.10 실행 기준 고정
- `main.py`를 기준 진입점으로 사용
- `config/devices.yaml`에서 장치 설정을 읽을 수 있는 구조 정의
- `asyncio` 기반 메인 루프 자리 마련
- `core`, `adapters`, `tui`, `tests` 디렉터리 책임 정리
- `requirements.txt`, `Dockerfile` 기본 실행 기준 정리

이번 작업에서 제외하는 항목:

- MQTT 실제 송수신 구현
- ESS 충방전 계산 로직
- 명령 처리 로직
- TUI 화면 구현

## 디렉터리 책임

- `main.py`: 애플리케이션 진입점, 설정 로딩, 구성 조립
- `config/`: 장치 설정, 시나리오 설정
- `core/`: ESS 순수 도메인 로직
- `adapters/`: MQTT 등 외부 입출력 연결
- `tui/`: 로컬 상태 확인 UI
- `tests/`: 단위 테스트
- `docs/`: 작업 기준 문서와 지라 정리 문서

## 구현 기준

### 0. 실행 환경

- Python 기준 버전은 `3.10`
- Docker 기준 이미지는 `python:3.10-slim`
- 설정 로딩은 `PyYAML`
- 설정 검증은 `pydantic`

### 1. main.py

`main.py`는 최소한 아래 순서로 동작해야 한다.

1. 설정 파일 경로 확인
2. 장치 설정 로드
3. 앱 컨텍스트 또는 서비스 객체 생성
4. 메인 asyncio 루프 시작
5. 종료 시 정리 루틴 호출

### 2. 설정 파일

`config/devices.yaml`에는 최소한 아래 정보가 들어갈 수 있어야 한다.

- `plant_id`
- `device_id`
- `resource_type`
- `publish_interval_sec`
- `initial_soc`
- `power_limit_kw`
- `low_soc_threshold`
- `high_soc_threshold`
- `min_safe_soc_threshold`
- `max_safe_soc_threshold`
- `mqtt_broker_host`
- `mqtt_broker_port`

### 3. 실행 루프

초기 단계에서는 전체 ESS 제어 로직이 완성되지 않아도 된다.

대신 아래 형태의 루프 자리는 있어야 한다.

- tick 단위 반복
- telemetry 발행 연결 가능
- MQTT command subscriber 연결 가능
- 로컬 CLI command 처리 가능
- graceful shutdown 가능

## 완료 조건

- `python main.py` 또는 동등한 실행 명령으로 프로세스가 시작된다.
- 설정 파일 로딩 실패 시 명확한 오류가 난다.
- 설정 파일 로딩 성공 시 앱이 실행 루프에 들어간다.
- 로컬 CLI에서 기본 command를 받을 수 있다.
- MQTT command 경로를 붙일 수 있는 구조가 있다.
- 디렉터리 책임이 문서와 코드 구조상 일치한다.
- 이후 작업인 MQTT, payload, ESS 계산 로직을 붙일 수 있는 상태다.

## 현재 결과

현재 기준으로 아래 항목이 반영되어 있다.

- Python 3.10 기준 Docker 실행 환경 정리
- `main.py` 부트스트랩 분리
- `runtime_config.py` 설정 로딩 및 검증 분리
- `simulator_app.py` 앱 조립 및 실행 루프 분리
- `config/devices.yaml` 기본 설정 작성
- 로컬 CLI 명령 입력 루프 연결
- MQTT publisher / subscriber 연결 지점 확보
- core 로직을 `validators.py`, `calculations.py`, `policies.py`로 분리

즉, 지라 1번인 `ESS 시뮬레이터 기본 실행 구조 구성` 기준으로는 완료 상태로 본다.

## 후속 작업 연결

이 작업이 끝나면 다음 순서로 진행한다.

1. MQTT 통신 규격 적용
2. ESS payload 모델 구현
3. ESS 충방전 및 SOC 계산 로직 구현
4. ESS 상태 전이 로직 구현
5. ESS 명령 처리기 구현

다음 작업 시작 기준은 `2장: ESS MQTT 통신 규격 적용`이다.

## 메모

현재 단계에서는 공통 `shared` 의존 없이 `ess-simulator` 내부에서 독립 실행 가능한 구조를 유지한다.

또한 로컬 명령과 EMS MQTT 명령이 결국 같은 command handler를 타도록 구성한다.
