# Testing Guide

## 개요

`load-simulator`는 `unittest` 기반으로 테스트를 구성합니다.

현재 테스트는 다음 범위를 포함합니다.

- 도메인 모델
- 상태 머신
- 시나리오 엔진
- 명령 처리
- MQTT 계약
- MQTT publisher
- MQTT subscriber
- runtime config
- simulator app
- main entrypoint parser

## 테스트 실행 방법

### 1. 기본 discover 실행

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\load-simulator
python -m unittest discover -s tests
```

### 2. 테스트 패키지 진입점 실행

```powershell
python -m tests
```

`tests/__main__.py`가 테스트 전체를 모아서 실행합니다.

## 주요 테스트 파일

- 도메인 모델:
  [test_load.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_load.py)
- 상태 머신:
  [test_state_machine.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_state_machine.py)
- 시나리오 엔진:
  [test_scenario.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_scenario.py)
- 명령 처리:
  [test_command_handler.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_command_handler.py)
- MQTT 계약:
  [test_mqtt_contract.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_mqtt_contract.py)
- publisher:
  [test_mqtt_publisher.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_mqtt_publisher.py)
- subscriber:
  [test_mqtt_subscriber.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_mqtt_subscriber.py)
- runtime config:
  [test_runtime_config.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_runtime_config.py)
- 앱 런타임:
  [test_simulator_app.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_simulator_app.py)
- main parser:
  [test_main.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/tests/test_main.py)

## 테스트에서 확인하는 것

### 도메인

- 다중 분전함 로드 가능 여부
- 중복 ID 검증
- 활성/비활성 장치 구분

### 시나리오

- 피크 시간대 소비 증가
- shed 반영 후 소비 감소
- 에너지 누적 계산

### 명령 처리

- 정상 `load_shed` 수용
- disabled device 거절
- 잘못된 비율 거절

### MQTT

- 토픽 파싱
- telemetry JSON shape
- ACK JSON shape
- subscriber가 실제 장치 상태를 바꾸는지

### 런타임

- 설정 파일 로드
- publish cycle 생성
- 앱 실행 시 시작/정리 호출

## 운영 전 확인 추천 순서

1. `python -m tests`
2. `python main.py --cycles 1`
3. `docker compose config`
4. broker가 있다면 `docker compose up --build`
