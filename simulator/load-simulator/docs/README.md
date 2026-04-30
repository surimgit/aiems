# Load Simulator Docs

`load-simulator`는 하나의 Edge 아래 여러 분전함을 `load device`로 시뮬레이션하는 소비 시뮬레이터입니다.

이 문서는 문서 진입점입니다. 실행 방법, 설정 방법, MQTT 규격, 내부 구조, 테스트 방법은 아래 문서를 따라가면 됩니다.

## 빠른 시작

로컬에서 바로 1사이클만 실행해 확인:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\load-simulator
python main.py --cycles 1
```

테스트 전체 실행:

```powershell
python -m unittest discover -s tests
python -m tests
```

Docker Compose 설정 확인:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator
docker compose config
```

## 어떤 문서를 보면 되는가

- 실행 방법과 운영 흐름이 궁금하면:
  [quick-start.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/quick-start.md)
- 설정 파일을 어떻게 작성하는지 보고 싶으면:
  [configuration-guide.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/configuration-guide.md)
- MQTT 토픽과 payload 형식을 확인하려면:
  [mqtt-guide.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/mqtt-guide.md)
- 내부 코드 구조와 런타임 흐름을 이해하려면:
  [runtime-architecture.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/runtime-architecture.md)
- 테스트를 어떻게 돌리고 어떤 범위를 검증하는지 보려면:
  [testing-guide.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/testing-guide.md)
- 다중 분전함 도메인 설계 기준 자체를 보려면:
  [multi-panel-domain-model.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/multi-panel-domain-model.md)

## 현재 구현 범위

- 한 `edge` 아래 여러 분전함 지원
- 분전함별 `device_id`, `panel_id` 지원
- 시나리오 기반 소비량 생성
- `load_shed` 명령 수신 및 `shed_ratio` 반영
- MQTT `telemetry / command / ack / heartbeat` 처리
- `topology` 서비스 연동: 선로 장애(wire_fault) 시 `P=0`, `comms_health="wire_fault"` 발행
- 로컬 실행 및 Docker 실행 경로 제공
- 단위 테스트 및 통합 성격 테스트 포함

## 관련 파일

- 실행 진입점:
  [main.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/main.py)
- 런타임 조립:
  [simulator_app.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/simulator_app.py)
- 설정 로드:
  [runtime_config.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/runtime_config.py)
- 장치/분전함 도메인:
  [core/load.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/load.py)
- 시나리오 엔진:
  [core/scenario.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/scenario.py)
- 명령 처리:
  [core/command_handler.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/command_handler.py)
- MQTT 계약:
  [mqtt_contract.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/mqtt_contract.py)
