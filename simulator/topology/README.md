# Topology 서비스

`topology`는 EMS 플랜트 내 선로(Line)와 스위치(Switch)의 상태를 관리하고,  
상태 변경을 MQTT retained 메시지로 발행하는 경량 HTTP + MQTT 서비스입니다.

## 역할

- 선로 장애(FAULT) / 운영자 차단(BLOCKED) / 정상(NORMAL) 상태 관리
- 스위치 OPEN / CLOSE 조작 처리
- 상태 변경 시 `{plant_id}/topology/line/{line_id}` 토픽으로 MQTT retained 발행
- 각 시뮬레이터는 이 토픽을 구독해 `wire_fault` 여부를 판단함

## 구조

```
topology/
├── main.py          # HTTP 서버 + MQTT 발행 로직
├── topology.yaml    # 선로/노드/스위치 초기 상태 (파일로 영속)
├── static/
│   └── index.html   # 토폴로지 상태 Web UI
├── Dockerfile
├── requirements.txt
└── tests/           # 통합 테스트 (run_tests.py)
```

## 실행

Docker Compose를 통해 자동으로 기동됩니다.

```bash
cd simulator/
docker compose up -d
```

직접 빌드:

```bash
docker build -t topology:latest ./topology
```

Web UI:

```
http://localhost:8081
```

## REST API

### 토폴로지 전체 조회

```
GET /api/topology
```

### 선로 장애 주입 / 복구

```
PATCH /api/lines/{line_id}
```

| Body | 설명 |
|---|---|
| `{"fault": true}` | 선로 FAULT 주입 |
| `{"fault": false}` | 선로 FAULT 복구 (NORMAL) |
| `{"command": "ISOLATE_LINE"}` | 운영자 차단 (BLOCKED) |
| `{"command": "RESTORE_LINE"}` | 운영자 차단 해제 (NORMAL) |

### 스위치 조작

```
PATCH /api/switches/{switch_id}
```

| Body | 설명 |
|---|---|
| `{"command": "OPEN_SWITCH"}` | 스위치 개방 |
| `{"command": "CLOSE_SWITCH"}` | 스위치 투입 |

### 선로 추가 / 삭제

```
POST   /api/lines        # 선로 추가
DELETE /api/lines/{line_id}  # 선로 삭제
```

## MQTT 토픽 구조

```
{plant_id}/topology/line/{line_id}    # 선로 상태 (retained)
{plant_id}/topology/switch/{switch_id} # 스위치 상태 (retained)
{plant_id}/topology/event              # 상태 변경 이벤트
```

### 선로 상태 payload 예시

```json
{
  "line_id": "line-solar01-ess01",
  "status": "FAULT",
  "from_node_id": "node-solar-01",
  "to_node_id": "node-ess-01",
  "affected_devices": ["solar-01", "ess-01"]
}
```

`status` 값: `NORMAL` | `FAULT` | `BLOCKED`

### 스위치 상태 payload 예시

```json
{
  "switch_id": "sw-solar01-ess01",
  "line_id": "line-solar01-ess01",
  "position": "OPEN",
  "affected_devices": ["solar-01", "ess-01"]
}
```

`position` 값: `CLOSED` | `OPEN` | `TRANSITIONING`

## 시뮬레이터의 wire_fault 판단 로직

각 시뮬레이터(solar, diesel, ess, load)는 `{plant_id}/topology/#`를 구독하고  
`_is_wire_fault(device_id)` 함수로 자신의 장애 여부를 판단합니다.

```
device_id가 affected_devices에 포함된 선로 중
  - line.status != NORMAL   →  wire_fault
  - switch.position != CLOSED  →  wire_fault
```

wire_fault 상태일 때 시뮬레이터 동작:

| 항목 | 정상 | wire_fault |
|---|---|---|
| `P` (유효전력) | 실제 발전/소비값 | `0.0` |
| `comms_health` | `"ok"` | `"wire_fault"` |
| ESS SOC | 변화 | 고정 (fault 진입 시점 값 유지) |

## 기본 토폴로지 (topology.yaml)

```
[solar-01] ──line-solar01-ess01── [ess-01]
[diesel-01] ──line-diesel01-ess01── [ess-01]
[ess-01] ──line-ess01-load01── [load-01]
```

각 선로에는 스위치가 하나씩 내장되어 있습니다.

## 통합 테스트

```bash
docker run --rm --network simulator_ems_default \
  -e MQTT_HOST=mqtt-broker \
  -e SM_URL=http://simulator-manager:8080 \
  -e TOPO_URL=http://topology:8081 \
  -v $(pwd)/tests:/tests -w /tests \
  python:3.10-slim sh -c "pip install paho-mqtt requests -q && python run_tests.py"
```

특정 시뮬레이터만 테스트:

```bash
python run_tests.py solar       # 시나리오 1~3
python run_tests.py ess         # 시나리오 4
python run_tests.py diesel      # 시나리오 5
python run_tests.py load        # 시나리오 6
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `PORT` | `8081` | HTTP 서버 포트 |
| `MQTT_HOST` | `mqtt-broker` | MQTT 브로커 호스트 |
| `MQTT_PORT` | `1883` | MQTT 브로커 포트 |
| `TOPOLOGY_PATH` | `/app/topology.yaml` | 선로 상태 파일 경로 |
