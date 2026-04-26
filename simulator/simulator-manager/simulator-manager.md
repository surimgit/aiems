# Simulator Manager

## 개요

`simulator-manager`는 EMS Edge 시뮬레이터를 동적으로 생성, 설정, 제어하는 관리 서비스입니다.

주요 역할은 다음과 같습니다.

- Web UI 또는 REST API로 Edge 시뮬레이터 컨테이너를 생성·삭제
- 각 Edge에 연결된 Device 목록을 YAML 파일로 관리
- Docker 소켓을 통해 Edge 컨테이너를 직접 기동·종료
- 매니저 재시작 시 기존 Edge를 자동으로 복구

현재 지원하는 Edge 타입은 `solar`, `diesel`, `ess`, `load`입니다.

## 구조

```
simulator-manager/
├── main.py          # HTTP 서버 및 전체 비즈니스 로직
├── static/
│   └── index.html   # Web UI (단일 페이지 앱)
├── edges/           # Edge별 설정 디렉터리 (런타임 생성)
│   └── {edge_id}/
│       ├── edge_info.json   # Edge 메타데이터
│       ├── devices.yaml     # Device 목록 및 파라미터
│       └── scenario.yaml    # load 타입 전용 시나리오 프로파일
├── requirements.txt
└── Dockerfile
```

## 빠른 시작

### 1. 사전 준비

아래 4개 시뮬레이터 이미지를 먼저 빌드해야 합니다.

```bash
cd simulator/

docker build -t solar-simulator:latest ./solar-simulator
docker build -t diesel-simulator:latest ./diesel-simulator
docker build -t ess-simulator:latest ./ess-simulator
docker build -t load-simulator:latest ./load-simulator
```

### 2. Docker Compose 실행

```bash
cd simulator/
docker compose up -d --build
```

실행되는 서비스:

- `mqtt-broker` — Eclipse Mosquitto 2.0 (포트 1883)
- `mqtt-logger` — 전체 토픽 구독 로그 출력
- `simulator-manager` — Web UI + REST API (포트 8080)

### 3. Web UI 접속

```
http://localhost:8080
```

브라우저에서 Edge를 추가하고 Device를 관리할 수 있습니다.

## Edge 타입별 동작

| 타입 | Docker 이미지 | 컨테이너 기동 커맨드 | Device 자동 생성 |
|---|---|---|---|
| solar | solar-simulator:latest | 기본 CMD | 없음 (수동 추가 필요) |
| diesel | diesel-simulator:latest | 기본 CMD | 없음 (수동 추가 필요) |
| ess | ess-simulator:latest | `python main.py --no-cli` | 없음 (수동 추가 필요) |
| load | load-simulator:latest | `python main.py --scenario /app/config/scenario.yaml` | 기본 Device 1개 자동 생성 |

load 타입은 Edge 생성 시 기본 Device(`{edge_id}-load-01`)를 자동으로 추가합니다.  
solar, diesel, ess 타입은 Edge 생성 후 Web UI 또는 API로 Device를 직접 추가해야 합니다.

## REST API

### Edge 목록 조회

```
GET /api/edges
```

응답 예시:

```json
[
  {
    "edge_id": "solar-edge-01",
    "edge_type": "solar",
    "plant_id": "PLANT-ALPHA",
    "mqtt_broker_host": "mqtt-broker",
    "mqtt_broker_port": 1883,
    "devices_count": 2,
    "status": "running"
  }
]
```

`status` 값은 Docker 컨테이너 상태를 그대로 반영합니다: `running`, `exited`, `restarting`, `not_found`

### Edge 생성

```
POST /api/edges
```

요청 바디:

```json
{
  "edge_id": "solar-edge-01",
  "edge_type": "solar",
  "plant_id": "PLANT-ALPHA",
  "mqtt_broker_host": "mqtt-broker",
  "mqtt_broker_port": 1883
}
```

- `edge_id`: 컨테이너 이름과 동일하게 사용됩니다. 중복 불가.
- `edge_type`: `solar`, `diesel`, `ess`, `load` 중 하나.
- `plant_id`: MQTT 토픽의 최상위 네임스페이스.
- `mqtt_broker_host`, `mqtt_broker_port`: 생략 시 기본값 `mqtt-broker`, `1883` 사용.

응답 예시:

```json
{
  "edge_id": "solar-edge-01",
  "status": "created"
}
```

Edge 생성 즉시 Docker 컨테이너가 기동됩니다.

### Edge 삭제

```
DELETE /api/edges/{edge_id}
```

컨테이너를 종료하고 설정 디렉터리를 삭제합니다.

응답 예시:

```json
{
  "edge_id": "solar-edge-01",
  "status": "deleted"
}
```

### Device 목록 조회

```
GET /api/edges/{edge_id}/devices
```

응답 예시 (solar 타입):

```json
[
  {
    "device_id": "solar-01",
    "panel_id": "PANEL-SOUTH",
    "rated_kw": 50.0,
    "irradiance_w_m2": 800,
    "temperature_c": 25
  }
]
```

### Device 추가

```
POST /api/edges/{edge_id}/devices
```

타입별 요청 바디는 아래 Device 스키마 섹션을 참고하세요.

응답 예시:

```json
{
  "device_id": "solar-01",
  "status": "added"
}
```

Device를 추가하면 해당 Edge의 `devices.yaml`이 즉시 갱신됩니다.  
solar, diesel 시뮬레이터는 파일 변경을 2초 주기로 감지해 hot-reload합니다.

### Device 삭제

```
DELETE /api/edges/{edge_id}/devices/{device_id}
```

응답 예시:

```json
{
  "device_id": "solar-01",
  "status": "removed"
}
```

## Device 스키마

### solar

```json
{
  "device_id": "solar-01",
  "panel_id": "PANEL-SOUTH",
  "rated_kw": 50.0,
  "irradiance_w_m2": 800,
  "temperature_c": 25
}
```

### diesel

```json
{
  "device_id": "diesel-01",
  "panel_id": "PANEL-GEN",
  "rated_kw": 200.0
}
```

### ess

```json
{
  "device_id": "ess-01",
  "resource_type": "ess",
  "publish_interval_sec": 0.5,
  "initial_soc": 62.0,
  "power_limit_kw": 42.0,
  "capacity_kwh": 420.0,
  "low_soc_threshold": 20.0,
  "high_soc_threshold": 90.0,
  "min_safe_soc_threshold": 10.0,
  "max_safe_soc_threshold": 95.0,
  "temperature_c": 24.5,
  "max_temperature_c": 45.0
}
```

### load

```json
{
  "device_id": "load-01",
  "panel_id": "PANEL-MAIN",
  "name": "office-panel",
  "rated_kw": 120.0,
  "base_kw": 80.0,
  "power_factor": 0.98,
  "voltage_v": 380.0,
  "frequency_hz": 60.0,
  "enabled": true,
  "scenario_profile": "office-day"
}
```

`scenario_profile`은 `office-day`, `hvac-heavy`, `off-hours` 중 하나입니다.

## MQTT 토픽 구조

모든 Edge 타입은 동일한 4단계 토픽 형식을 사용합니다.

```text
{plant_id}/{resource_type}/{device_id}/{message_type}
```

| 항목 | 설명 |
|---|---|
| `plant_id` | Edge 생성 시 지정한 값 (예: `PLANT-ALPHA`) |
| `resource_type` | Edge 타입과 동일 (`solar`, `diesel`, `ess`, `load`) |
| `device_id` | Device 추가 시 지정한 값 |
| `message_type` | `telemetry`, `command`, `ack`, `event`, `emergency` |

예시:

```text
PLANT-ALPHA/solar/solar-01/telemetry
PLANT-ALPHA/diesel/diesel-01/telemetry
PLANT-ALPHA/ess/ess-01/telemetry
PLANT-ALPHA/load/load-01/telemetry
```

Heartbeat는 사이트 단위로 발행합니다.

```text
{plant_id}/heartbeat
```

예시: `PLANT-ALPHA/heartbeat`

### device_id 유일성 규칙

`edge_id`는 MQTT 토픽에 포함되지 않습니다.  
따라서 같은 `plant_id`와 `resource_type` 내에서 `device_id`가 겹치면 토픽이 충돌합니다.

```text
# 충돌 예시 — 두 Edge가 동일 토픽으로 발행
solar-edge-01 / device_id: solar-01  →  PLANT-ALPHA/solar/solar-01/telemetry
solar-edge-02 / device_id: solar-01  →  PLANT-ALPHA/solar/solar-01/telemetry  ← 충돌

# 정상 예시
solar-edge-01 / device_id: solar-01  →  PLANT-ALPHA/solar/solar-01/telemetry
solar-edge-02 / device_id: solar-02  →  PLANT-ALPHA/solar/solar-02/telemetry
```

서로 다른 `resource_type`이라면 동일한 `device_id`를 사용해도 토픽이 분리됩니다.

```text
solar-edge-01 / device_id: gen-01  →  PLANT-ALPHA/solar/gen-01/telemetry
diesel-edge-01 / device_id: gen-01  →  PLANT-ALPHA/diesel/gen-01/telemetry  ← 충돌 없음
```

## MQTT 메시지 모니터링

모든 토픽을 실시간으로 확인하려면:

```bash
docker logs mqtt-logger -f
```

특정 토픽만 필터링하려면:

```bash
docker exec mqtt-broker mosquitto_sub -h localhost -t "PLANT-ALPHA/solar/#" -v
docker exec mqtt-broker mosquitto_sub -h localhost -t "PLANT-ALPHA/#" -v
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PORT` | `8080` | HTTP 서버 포트 |
| `DOCKER_NETWORK` | `ems_default` | Edge 컨테이너가 참여할 Docker 네트워크 |
| `SOLAR_IMAGE` | `solar-simulator:latest` | solar 컨테이너 이미지 |
| `DIESEL_IMAGE` | `diesel-simulator:latest` | diesel 컨테이너 이미지 |
| `ESS_IMAGE` | `ess-simulator:latest` | ess 컨테이너 이미지 |
| `LOAD_IMAGE` | `load-simulator:latest` | load 컨테이너 이미지 |
| `EDGES_HOST_PATH` | 자동 감지 | 호스트의 `edges/` 절대 경로 (컨테이너 볼륨 마운트용) |

`DOCKER_NETWORK`와 `EDGES_HOST_PATH`는 컨테이너 기동 시 Docker 소켓을 통해 자동으로 감지합니다.  
정확한 값을 명시하고 싶을 때만 환경 변수로 지정하면 됩니다.

## 코드 구조

- `main.py`
  - `_detect_real_network_name()` — 컨테이너 자신의 네트워크 이름 자동 감지
  - `_detect_host_edges_path()` — 호스트의 `edges/` 경로 자동 감지
  - `create_edge()` — Edge 디렉터리 생성, YAML 작성, 컨테이너 기동
  - `delete_edge()` — 컨테이너 종료, 디렉터리 삭제
  - `add_device()` / `remove_device()` — `devices.yaml` CRUD
  - `_start_existing_edges()` — 매니저 시작 시 기존 Edge 자동 복구
  - `Handler` — ThreadingHTTPServer 기반 HTTP 라우터
- `static/index.html`
  - Edge 목록 및 상태 표시 (5초 주기 자동 갱신)
  - Edge / Device 생성·삭제 모달

## 문제 해결

### Edge 생성 후 컨테이너가 바로 재시작을 반복함

```bash
docker logs {edge_id}
```

로그를 확인합니다. 주로 두 가지 원인입니다.

1. **`devices.yaml` 필드 누락** — 특히 load 타입은 `name`, `rated_kw`, `power_factor`, `voltage_v`, `frequency_hz`, `scenario_profile`이 모두 필요합니다.
2. **이미지 미빌드** — `docker images`로 해당 타입의 이미지가 존재하는지 확인합니다.

### Device를 추가했는데 MQTT에 데이터가 안 나옴

1. `docker ps`로 해당 Edge 컨테이너가 `running` 상태인지 확인합니다.
2. `docker logs {edge_id}`에서 `[hot-reload] Device added:` 메시지가 나왔는지 확인합니다.
3. solar, diesel은 파일 변경을 2초 주기로 감지합니다. 잠시 대기 후 다시 확인합니다.

### MQTT 로그에서 특정 Edge의 데이터를 구분할 수 없음

`device_id`가 다른 Edge와 중복되지 않았는지 확인합니다.  
같은 `plant_id` + `resource_type` 조합에서 `device_id`는 전체에서 유일해야 합니다.

### `docker logs`에 아무것도 안 나옴

시뮬레이터 이미지에 `PYTHONUNBUFFERED=1`이 설정되어 있지 않으면 Python stdout이 버퍼링됩니다.  
각 시뮬레이터의 Dockerfile에 다음을 추가한 뒤 이미지를 재빌드하세요.

```dockerfile
ENV PYTHONUNBUFFERED=1
```

## 관련 파일

- [docker-compose.yml](../docker-compose.yml)
- [solar-simulator](../solar-simulator/)
- [diesel-simulator](../diesel-simulator/)
- [ess-simulator/docs/mqtt-contract-application.md](../ess-simulator/docs/mqtt-contract-application.md)
- [load-simulator/docs/mqtt-guide.md](../load-simulator/docs/mqtt-guide.md)
