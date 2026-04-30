# Runtime Architecture

## 개요

`load-simulator`의 런타임은 아래 계층으로 구성됩니다.

1. 설정 로드
2. 도메인 모델 생성
3. 시나리오 엔진 tick
4. MQTT publish / subscribe
5. 명령 반영 후 다음 tick에 상태 반영

## 핵심 파일

- 실행 진입점:
  [main.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/main.py)
- 런타임 설정 로더:
  [runtime_config.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/runtime_config.py)
- 앱 조립:
  [simulator_app.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/simulator_app.py)
- 분전함 도메인:
  [core/load.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/load.py)
- 상태 전이:
  [core/state_machine.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/state_machine.py)
- 시나리오 엔진:
  [core/scenario.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/scenario.py)
- 명령 처리:
  [core/command_handler.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/core/command_handler.py)

## 런타임 흐름

### 1. main.py

`main.py`는 CLI 인자를 읽고 `RuntimeConfig`를 만든 뒤 `LoadSimulatorApp`을 실행합니다.

### 2. runtime_config.py

`devices.yaml`과 `scenario.yaml`을 읽어서 아래를 조립합니다.

- `site_id`
- `edge_id`
- MQTT broker 정보
- publish 주기
- `LoadFleet`
- 시나리오 프로파일 사전

### 3. core/load.py

도메인 모델은 다음으로 구성됩니다.

- `LoadDeviceConfig`
- `LoadMeasurement`
- `LoadState`
- `LoadDevice`
- `LoadFleet`

핵심 포인트:

- 분전함 1개 = `LoadDevice` 1개
- 여러 분전함은 `LoadFleet`에서 관리

### 4. core/scenario.py

`LoadScenarioEngine`은 활성 분전함에 대해 매 tick마다 전기 측정값을 계산합니다.

반영 요소:

- 피크 시간대
- 비피크 시간대
- 주말 배수
- 노이즈
- 최소 부하 하한
- 현재 `shed_ratio`

### 5. core/command_handler.py

`load_shed` 명령이 들어오면:

1. 분전함 존재 여부 확인
2. 활성화 여부 확인
3. `reduction_ratio` 검증
4. `shed_ratio` 상태 반영
5. ACK 반환

### 6. simulator_app.py

`LoadSimulatorApp`는 다음을 수행합니다.

- publisher 시작
- subscriber 시작
- 시나리오 tick
- telemetry / heartbeat 직렬화
- publish
- 종료 시 자원 정리

## 상태 변화 예시

1. 초기 활성 장치
   - `IDLE`
2. 시나리오 tick 후 전력 생성
   - `RUNNING`
3. `load_shed` 명령 적용
   - `SHED`
4. 이후 시나리오 계산
   - 줄어든 부하 반영

## 설계 참고 문서

다중 분전함 모델의 설계 기준 자체는 아래 문서에 정리되어 있습니다.

- [multi-panel-domain-model.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/multi-panel-domain-model.md)
