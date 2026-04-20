# ESS MQTT 통신 규격 적용

## 목적

이 문서는 ESS 시뮬레이터에 반영된 MQTT 계약 구현 결과를 정리한다.
기준 문서는 외부 설계 문서의 아래 항목이다.

- `05-data-contracts/mqtt-contract.md`
- `05-data-contracts/message-schema.md`
- `08-domain-detail/telemetry-payload.md`

## 반영 범위

현재 구현에는 아래 항목이 반영되어 있다.

- 일반 MQTT topic 규격 적용
- heartbeat 전용 topic 규격 적용
- ESS command payload 검증
- ESS telemetry payload 직렬화
- ACK payload 직렬화
- heartbeat payload 직렬화
- MQTT subscriber / publisher 경계 분리
- snapshot -> telemetry mapper 분리

## Topic

일반 토픽 규격:

```text
{plant_id}/{resource_type}/{device_id}/{message_type}
```

ESS 시뮬레이터가 사용하는 토픽:

- command subscribe: `{plant_id}/ess/{device_id}/command`
- telemetry publish: `{plant_id}/ess/{device_id}/telemetry`
- ack publish: `{plant_id}/ess/{device_id}/ack`

heartbeat 토픽은 문서 기준으로 예외 규격을 사용한다.

- heartbeat publish: `{plant_id}/heartbeat`

## ESS Command

현재 MQTT 명령은 `ess_mode` 한 종류를 계약으로 고정했다.

```json
{
  "command_id": "cmd-042",
  "command_type": "ess_mode",
  "payload": {
    "mode": "charge",
    "target_power_kw": 30.0
  }
}
```

구현 정책:

- `mode` 는 `charge`, `discharge`, `standby` 만 허용
- `target_power_kw` 는 0 이상
- 문서에 없는 필드는 거부

## Telemetry

현재 telemetry 직렬화 형식은 아래와 같다.

```json
{
  "device_id": "ess-01",
  "plant_id": "PLANT-ALPHA",
  "resource_type": "ess",
  "timestamp": "2026-04-14T07:50:00Z",
  "data": {
    "instantaneous": {
      "P": 30.0,
      "Q": 0.0,
      "V": 380.0,
      "I": 0.079,
      "f": 60.0,
      "PF": 1.0
    },
    "energy": {
      "kWh": 820.0,
      "kvarh": 0.0
    },
    "status": {
      "SOC": 67.3,
      "operating_mode": "discharge",
      "comms_health": "ok"
    }
  }
}
```

구현 정책:

- `timestamp` 는 UTC ISO 8601 `Z` 형식 사용
- ESS `P` 부호는 현재 코드 기준으로 문서 규칙을 따른다
- telemetry는 `snapshot_to_telemetry()` 에서 일괄 변환

## ACK

ACK는 명령 수신 즉시 발행한다.

```json
{
  "command_id": "cmd-042",
  "status": "accepted"
}
```

거부 시:

```json
{
  "command_id": "cmd-042",
  "status": "rejected",
  "reason": "..."
}
```

## Heartbeat

heartbeat는 시뮬레이터 생존 신호다.
문서에 payload 상세가 강하게 정의되어 있지 않아, 현재 구현은 최소 필드만 사용한다.

토픽:

```text
{plant_id}/heartbeat
```

payload:

```json
{
  "plant_id": "PLANT-ALPHA",
  "resource_type": "ess",
  "device_id": "ess-01",
  "timestamp": "2026-04-14T07:50:00Z",
  "status": "alive"
}
```

## 코드 위치

- `mqtt_contract.py`
  - topic parser / builder
  - command / telemetry / ack / heartbeat 모델
  - snapshot -> telemetry 변환
- `adapters/inbound/mqtt_subscriber.py`
  - MQTT command 검증
  - invalid payload rejected ACK 처리
- `adapters/outbound/mqtt_publisher.py`
  - telemetry / ack / heartbeat publish
- `adapters/outbound/heartbeat_publisher.py`
  - heartbeat topic / payload helper
- `simulator_app.py`
  - telemetry / heartbeat 주기 발행

## 테스트 범위

테스트는 아래 3단계로 구성한다.

- `tests/unit`
  - topic, payload, mapper 검증
- `tests/integration`
  - subscriber / publisher 검증
- `tests/functional`
  - command 수신부터 ACK와 상태 반영까지 검증

실행:

```bash
python -m tests
```

## 비범위

이 문서는 MQTT 경계 계약까지만 다룬다.
아래 항목은 다음 작업 범위다.

- 상태 전이 고도화
- command result 이벤트
- reason code 체계화
- SOC 계산 세부 고도화
