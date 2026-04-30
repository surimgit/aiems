# EMS Edge Simulator

`simulator/` contains the local MQTT broker, topology service, and edge simulators used for EMS integration testing.

## 포함 서비스

| 서비스 | 포트 | 설명 |
|---|---|---|
| `mqtt-broker` | 1883 | Eclipse Mosquitto 2.0 브로커 |
| `mqtt-logger` | — | 전체 토픽 구독 로그 출력 |
| `simulator-manager` | 8080 | Edge 컨테이너 생성·삭제 Web UI + REST API |
| `topology` | 8081 | 선로·스위치 상태 관리 + wire_fault MQTT 발행 |

Edge 시뮬레이터는 `simulator-manager`가 동적으로 Docker 컨테이너로 기동합니다.

| 이미지 | 설명 |
|---|---|
| `solar-simulator:latest` | 태양광 발전 시뮬레이터 |
| `diesel-simulator:latest` | 디젤 발전기 시뮬레이터 |
| `ess-simulator:latest` | 에너지 저장 장치 시뮬레이터 |
| `load-simulator:latest` | 부하 소비 시뮬레이터 |

## 빠른 시작

### 1. 시뮬레이터 이미지 빌드

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

실행 후 접속:

- 시뮬레이터 매니저 Web UI: `http://localhost:8080`
- 토폴로지 Web UI: `http://localhost:8081`

### 3. MQTT 로그 확인

```bash
docker logs mqtt-logger -f
```

## Wire Fault (선로 장애) 시뮬레이션

`topology` 서비스를 통해 선로 장애와 스위치 조작을 시뮬레이션할 수 있습니다.  
장애 발생 시 해당 선로에 연결된 시뮬레이터는 `P=0`, `comms_health=wire_fault`를 발행합니다.

```bash
# 선로 장애 주입
curl -X PATCH http://localhost:8081/api/lines/line-solar01-ess01 \
  -H "Content-Type: application/json" \
  -d '{"fault": true}'

# 선로 복구
curl -X PATCH http://localhost:8081/api/lines/line-solar01-ess01 \
  -H "Content-Type: application/json" \
  -d '{"fault": false}'

# 스위치 열기
curl -X PATCH http://localhost:8081/api/switches/sw-solar01-ess01 \
  -H "Content-Type: application/json" \
  -d '{"command": "OPEN_SWITCH"}'
```

## 각 서비스 문서

- [simulator-manager/simulator-manager.md](simulator-manager/simulator-manager.md)
- [topology/README.md](topology/README.md)
- [ess-simulator/docs/README.md](ess-simulator/docs/README.md)
- [load-simulator/docs/README.md](load-simulator/docs/README.md)
