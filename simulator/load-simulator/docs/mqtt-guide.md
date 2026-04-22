# MQTT Guide

## 개요

`load-simulator`는 MQTT 브로커와 다음 메시지를 주고받습니다.

- telemetry
- command
- ack
- heartbeat

구현 기준 코드는 [mqtt_contract.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/mqtt_contract.py)입니다.

## 1. 토픽 규칙

기본 토픽 형식:

```text
{site_id}/load/{device_id}/{message_type}
```

예시:

- `PLANT-ALPHA/load/load-01/telemetry`
- `PLANT-ALPHA/load/load-02/command`
- `PLANT-ALPHA/load/load-01/ack`

heartbeat는 site 단위로 발행합니다.

```text
{site_id}/heartbeat
```

예시:

- `PLANT-ALPHA/heartbeat`

## 2. Telemetry

Telemetry는 분전함별로 발행됩니다.

예시 구조:

```json
{
  "device_id": "load-01",
  "plant_id": "PLANT-ALPHA",
  "resource_type": "load",
  "timestamp": "2026-04-22T03:30:00Z",
  "data": {
    "instantaneous": {
      "P": 68.8,
      "Q": 13.9,
      "V": 380.0,
      "I": 106.2,
      "f": 60.0,
      "PF": 0.98
    },
    "energy": {
      "kWh": 0.019,
      "kvarh": 0.0019,
      "demand_max": 68.8
    },
    "status": {
      "comms_health": "ok",
      "operating_state": "RUNNING",
      "shed_ratio": 0.0,
      "panel_id": "panel-01"
    }
  }
}
```

## 3. Command

현재 지원 명령은 `load_shed`입니다.

예시:

```json
{
  "command_id": "cmd-001",
  "command_type": "load_shed",
  "payload": {
    "reduction_ratio": 0.3
  }
}
```

의미:

- `reduction_ratio=0.3`
  - 이후 시나리오 계산 시 해당 분전함 부하를 30% 줄임

## 4. ACK

명령 처리 결과는 분전함별 ACK 토픽으로 응답합니다.

성공 예시:

```json
{
  "command_id": "cmd-001",
  "status": "accepted"
}
```

실패 예시:

```json
{
  "command_id": "cmd-002",
  "status": "rejected",
  "reason": "INVALID_REDUCTION_RATIO"
}
```

대표 rejection reason:

- `DEVICE_NOT_FOUND`
- `DEVICE_DISABLED`
- `INVALID_COMMAND_PAYLOAD`
- `INVALID_REDUCTION_RATIO`
- `UNSUPPORTED_COMMAND_TYPE`

## 5. Heartbeat

Heartbeat는 사이트 생존 신호용 메시지입니다.

예시:

```json
{
  "plant_id": "PLANT-ALPHA",
  "resource_type": "load",
  "device_id": "load-01",
  "timestamp": "2026-04-22T03:30:00Z",
  "status": "alive"
}
```

## 6. 관련 코드

- 토픽/페이로드 계약:
  [mqtt_contract.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/mqtt_contract.py)
- publish:
  [adapters/outbound/mqtt_publisher.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/adapters/outbound/mqtt_publisher.py)
- subscribe:
  [adapters/inbound/mqtt_subscriber.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/simulator/load-simulator/adapters/inbound/mqtt_subscriber.py)
