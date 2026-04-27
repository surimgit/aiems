# ESS Simulator Docs

## 개요

`simulator/ess-simulator`는 ESS 단독 시뮬레이터입니다.

현재 버전의 목적은 다음과 같습니다.

- ESS 저장소 여러 개를 한 엣지 아래에서 동시에 시뮬레이션
- 각 저장소의 `SOC`, `power_kw`, `temperature_c`, `operating_mode`를 자동 생성
- 생성된 값을 MQTT 브로커로 telemetry/heartbeat 형태로 발행
- TUI에서 여러 저장소 상태를 한눈에 확인

`topology` 서비스와 연동해 선로 장애(wire_fault) 상태를 구독하고,  
장애 시 `power_kw=0`, `comms_health="wire_fault"`, SOC 고정 동작을 수행합니다.

## Wire Fault 동작

`topology` 서비스가 발행하는 `{plant_id}/topology/#` 토픽을 구독합니다.  
연결된 선로가 FAULT 또는 BLOCKED 상태이거나 스위치가 OPEN이면 wire_fault로 판단합니다.

| 상태 | `power_kw` | `comms_health` | SOC |
|---|---|---|---|
| 정상 | 실제 계산값 | `"ok"` | 정상 변화 |
| wire_fault | `0.0` | `"wire_fault"` | 진입 시점 값 고정 |

## 현재 구조

- `core/ess.py`
  ESS 상태, SOC 계산, safety rule 적용
- `core/profile_engine.py`
  상태 생성기 인터페이스
- `core/profiles/default_profile.py`
  기본 시간 기반 상태 생성 수식
- `adapters/outbound/mqtt_publisher.py`
  telemetry / ack / heartbeat 발행
- `adapters/inbound/mqtt_subscriber.py`
  MQTT command 수신 후 `device_id` 기준 라우팅
- `simulator_app.py`
  다중 ESS 디바이스 런타임
- `tui/app.py`
  ESS fleet 상태 확인용 TUI
- `config/devices.yaml`
  엣지에 연결된 ESS 디바이스 목록과 파라미터 설정

## 실행 전 준비

### 1. Python 의존성 설치

`ess-simulator`를 실행하는 Python 환경에 의존성을 설치해야 합니다.

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\ess-simulator
python -m pip install -r requirements.txt
```

주의:

- 반드시 `python main.py`를 실행할 때와 같은 `python`으로 설치해야 합니다.
- `ModuleNotFoundError: No module named 'paho'` 또는 `textual` 오류가 나면 대부분 이 단계 문제입니다.

### 2. Docker 준비

현재 compose는 다음 3개만 올립니다.

- `mqtt-broker`
- `mqtt-logger`
- `ess-simulator`

즉, ESS 런타임은 Docker로 올리고 TUI는 호스트 터미널에서 실행하는 구조입니다.

실행:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator
docker compose up --build
```

Docker Desktop이 꺼져 있으면 실행이 실패합니다.

## 실행 방법

### 1. ESS 시뮬레이터 실행

#### 방법 A. Docker compose 사용

가장 권장되는 방식입니다.

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator
docker compose up --build
```

이 경우 ESS 런타임은 컨테이너 안에서
`/app/config/devices.docker.yaml`을 사용합니다.

#### 방법 B. 로컬 Python 실행

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\ess-simulator
python main.py
```

기본적으로 [config/devices.yaml](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/config/devices.yaml) 을 읽습니다.

다른 설정 파일을 쓰고 싶으면:

```powershell
python main.py --config C:\path\to\devices.yaml
```

### 2. TUI 실행

TUI는 Docker 컨테이너로 올리지 않고, 로컬 터미널에서 실행합니다.

별도 터미널에서:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\ess-simulator
python tui\app.py
```

이 화면은 GUI 앱이 아니라 터미널 기반 TUI입니다.
즉, 실행한 콘솔 창 자체가 화면입니다.

## 기본 동작 방식

현재 설정은 ESS 저장소 4개를 가정합니다.

- `ess-01`
- `ess-02`
- `ess-03`
- `ess-04`

각 저장소는 독립적으로 다음 값을 생성합니다.

- `SOC`
- `power_kw`
- `temperature_c`
- `operating_mode`
- `state`
- `accumulated_energy_kwh`

생성 로직은 시간대 기반 기본 곡선 + 랜덤 진동으로 구성됩니다.

예시:

- 어떤 시간대에는 충전 위주
- 어떤 시간대에는 방전 위주
- `SOC`가 너무 높으면 충전 억제
- `SOC`가 너무 낮으면 방전 억제
- `power_kw`는 `power_limit_kw` 범위 안에서만 움직임

즉, 실제 설비가 아직 연결되지 않아도 "보기 그럴싸한" ESS 상태를 계속 발행합니다.

## MQTT 연결 구조

토픽 구조는 다음 형식을 따릅니다.

```text
{plant_id}/{resource_type}/{device_id}/{message_type}
```

ESS 예시:

- telemetry: `PLANT-ALPHA/ess/ess-01/telemetry`
- command: `PLANT-ALPHA/ess/ess-01/command`
- ack: `PLANT-ALPHA/ess/ess-01/ack`
- heartbeat: `PLANT-ALPHA/heartbeat`

현재 TUI는 아래 topic을 구독합니다.

- `PLANT-ALPHA/ess/+/telemetry`
- `PLANT-ALPHA/ess/+/ack`

즉, ESS 저장소가 여러 개여도 한 화면에서 동시에 확인할 수 있습니다.

Docker compose를 사용할 때도 TUI는 호스트에서 `localhost:1883` 브로커로 붙습니다.

## 엣지에 ESS 저장소를 더 연결하는 방법

현재 기준에서 "엣지에 저장소를 더 연결한다"는 의미는
[config/devices.yaml](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/config/devices.yaml)
의 `devices:` 목록에 항목을 추가하는 것입니다.

예시:

```yaml
plant_id: PLANT-ALPHA
mqtt_broker_host: localhost
mqtt_broker_port: 1883
devices:
  - device_id: ess-01
    resource_type: ess
    publish_interval_sec: 0.5
    initial_soc: 62.0
    power_limit_kw: 42.0
    capacity_kwh: 420.0
    low_soc_threshold: 20.0
    high_soc_threshold: 90.0
    min_safe_soc_threshold: 10.0
    max_safe_soc_threshold: 95.0
    temperature_c: 24.5
    max_temperature_c: 45.0
    profile:
      module: core.profiles.default_profile
      class_name: DefaultEssProfile
      seed: 101

  - device_id: ess-05
    resource_type: ess
    publish_interval_sec: 0.5
    initial_soc: 55.0
    power_limit_kw: 40.0
    capacity_kwh: 410.0
    low_soc_threshold: 20.0
    high_soc_threshold: 90.0
    min_safe_soc_threshold: 10.0
    max_safe_soc_threshold: 95.0
    temperature_c: 25.0
    max_temperature_c: 45.0
    profile:
      module: core.profiles.default_profile
      class_name: DefaultEssProfile
      seed: 505
```

추가 시 지켜야 할 점:

- `device_id`는 plant 내에서 유일해야 함
- `resource_type`는 현재 `ess`만 사용
- `power_limit_kw`, `capacity_kwh`, `publish_interval_sec`는 양수여야 함
- `high_soc_threshold > low_soc_threshold`
- `max_safe_soc_threshold > min_safe_soc_threshold`

설정 변경 후에는 시뮬레이터와 TUI를 재시작하면 됩니다.

Docker로 띄우는 경우에는
[devices.docker.yaml](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/config/devices.docker.yaml)
도 함께 반영해야 합니다.

즉:

- 로컬 실행만 쓸 경우: `devices.yaml` 수정
- Docker compose 실행도 쓸 경우: `devices.yaml`, `devices.docker.yaml` 둘 다 수정

## 상태 생성 수식 파일 교체 방법

현재 기본 상태 생성기는 아래 파일입니다.

- [default_profile.py](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/core/profiles/default_profile.py)

이 파일은 나중에 교체할 수 있도록 모듈화되어 있습니다.

교체 절차:

1. `core/profiles/` 아래 새 Python 파일 작성
2. `generate(context)` 메서드를 가진 클래스 구현
3. `devices.yaml`의 `profile.module`, `profile.class_name` 변경

예:

```yaml
profile:
  module: core.profiles.my_custom_profile
  class_name: MyCustomProfile
  seed: 777
```

즉, 상태 생성 수식을 바꾸고 싶을 때 시뮬레이터 본체를 크게 고치지 않아도 됩니다.

## 테스트

`ess-simulator` 디렉터리에서 실행:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\ess-simulator
python -m unittest tests.unit.test_simulator_app tests.integration.test_mqtt_subscriber tests.functional.test_ess_mqtt_flow tests.unit.test_mqtt_contract tests.unit.test_state_machine tests.unit.test_ess_state_logic
```

## 문제 해결

### `No module named 'paho'`

현재 `python` 환경에 패키지가 설치되지 않은 상태입니다.

```powershell
python -m pip install -r requirements.txt
```

### `No module named 'textual'`

TUI 실행 환경에 `textual`이 없는 상태입니다.

```powershell
python -m pip install -r requirements.txt
```

### Docker 브로커 연결 실패

예:

```text
failed to connect to the docker API
```

이 경우 Docker Desktop이 꺼져 있을 가능성이 큽니다.

### TUI는 뜨는데 데이터가 안 보임

다음 순서로 확인합니다.

1. MQTT 브로커가 실행 중인지 확인
2. `docker compose up` 또는 `python main.py` 중 하나로 ESS 런타임이 실제로 떠 있는지 확인
3. `config/devices.yaml`의 broker host/port가 맞는지 확인
4. TUI를 별도 터미널에서 실행했는지 확인

## 관련 문서

권장 읽기 순서:

1. [implementation-status.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/implementation-status.md)
2. [project-structure.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/project-structure.md)
3. [mqtt-contract-application.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/mqtt-contract-application.md)
4. [ess-state-model-application.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/ess-state-model-application.md)
5. [ess-charge-discharge-application.md](/C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/ess-simulator/docs/ess-charge-discharge-application.md)
