# Configuration Guide

## 개요

`load-simulator`는 두 개의 주요 설정 파일을 사용합니다.

- `config/devices.yaml`
- `config/scenario.yaml`

Docker 실행 시에는 broker host가 다른 [devices.docker.yaml](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/config/devices.docker.yaml)을 사용합니다.

## 1. devices.yaml

역할:

- site / edge 식별
- MQTT broker 정보
- publish 주기
- 분전함 목록

예시:

```yaml
site_id: PLANT-ALPHA
edge_id: edge-01
mqtt_broker_host: localhost
mqtt_broker_port: 1883
publish_interval_sec: 1.0

loads:
  - device_id: load-01
    panel_id: panel-01
    name: office-panel
    rated_kw: 120.0
    base_kw: 80.0
    power_factor: 0.98
    voltage_v: 380.0
    frequency_hz: 60.0
    enabled: true
    scenario_profile: office-day
```

### 필드 설명

- `site_id`
  - 플랜트 식별자
- `edge_id`
  - 해당 시뮬레이터가 표현하는 edge 식별자
- `mqtt_broker_host`
  - 로컬 실행 시 보통 `localhost`
- `mqtt_broker_port`
  - 기본 `1883`
- `publish_interval_sec`
  - 런타임 publish 주기
- `loads`
  - 분전함 목록

### 분전함 필드

- `device_id`
  - MQTT 토픽 식별자
- `panel_id`
  - 도메인 상 분전함 식별자
- `name`
  - 표시용 이름
- `rated_kw`
  - 분전함 최대 허용 전력
- `base_kw`
  - 기본 부하
- `power_factor`
  - 역률
- `voltage_v`
  - 전압
- `frequency_hz`
  - 주파수
- `enabled`
  - 비활성화 시 publish 대상 제외
- `scenario_profile`
  - `scenario.yaml`의 프로파일 이름

## 2. scenario.yaml

역할:

- 분전함별 소비 패턴 정의
- 피크/비피크/주말/최소 부하/노이즈 설정

예시:

```yaml
profiles:
  office-day:
    noise_ratio: 0.05
    peak_hours: [9, 10, 11, 14, 15, 16]
    peak_multiplier: 1.20
    off_peak_multiplier: 0.85
    weekend_multiplier: 0.70
    minimum_load_ratio: 0.15
```

### 필드 설명

- `noise_ratio`
  - 결정적 노이즈 반영 비율
- `peak_hours`
  - 피크 시간대 목록
- `peak_multiplier`
  - 피크 시간대 배수
- `off_peak_multiplier`
  - 비피크 시간대 배수
- `weekend_multiplier`
  - 주말 배수
- `minimum_load_ratio`
  - 정격 대비 최소 부하 하한

## 3. Docker 설정

Docker에서는 `mqtt_broker_host`가 `localhost`가 아니라 `mqtt-broker`여야 하므로 별도 파일을 둡니다.

- 로컬:
  [devices.yaml](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/config/devices.yaml)
- Docker:
  [devices.docker.yaml](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/config/devices.docker.yaml)

## 4. 설정 시 주의할 점

- `device_id`는 중복되면 안 됩니다.
- `panel_id`도 같은 edge 안에서 중복되면 안 됩니다.
- `base_kw <= rated_kw`를 만족해야 합니다.
- `scenario_profile`은 반드시 `scenario.yaml`에 정의돼 있어야 합니다.
- `enabled=false` 분전함은 로드되지만 발행 대상에서는 제외됩니다.
