# Quick Start

## 1. 로컬 실행

기본 설정 파일로 실행:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\load-simulator
python main.py
```

1회 또는 몇 회만 실행해서 동작을 빠르게 확인:

```powershell
python main.py --cycles 1
python main.py --cycles 3
```

직접 설정 파일 경로를 지정하고 싶으면:

```powershell
python main.py --config .\config\devices.yaml --scenario .\config\scenario.yaml --cycles 3
```

## 2. 실행 시 기대 동작

실행하면 다음 흐름으로 동작합니다.

1. `devices.yaml`, `scenario.yaml`을 읽어 분전함 목록과 시나리오 프로파일을 로드합니다.
2. 활성화된 분전함만 대상으로 시나리오 tick을 수행합니다.
3. 각 분전함의 telemetry JSON과 heartbeat JSON을 만듭니다.
4. MQTT broker에 연결 가능하면 publish합니다.
5. broker가 없으면 연결 실패 로그만 남기고 시뮬레이션 자체는 진행합니다.

## 3. Docker 실행

단독 이미지 빌드:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator\load-simulator
docker build -t load-simulator .
```

상위 compose로 전체 스택 실행:

```powershell
cd C:\Users\SSAFY\PycharmProjects\S14P31S305\simulator
docker compose up --build
```

이때 `load-simulator`는 `/app/config/devices.docker.yaml`을 사용합니다.

## 4. MQTT broker가 없을 때

로컬에 broker가 없으면 아래와 같은 형태로 연결 거부 로그가 나올 수 있습니다.

- publisher connection skipped
- subscriber connection skipped

이 경우는 코드 문제라기보다 broker 미기동 상태입니다.
시뮬레이터 계산과 콘솔 로그는 그대로 동작합니다.

## 5. 다음에 볼 문서

- 설정 파일 작성법:
  [configuration-guide.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/configuration-guide.md)
- MQTT 토픽/메시지 규격:
  [mqtt-guide.md](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/docs/mqtt-guide.md)
