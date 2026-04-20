# ESS MQTT 통신 규격 적용

## 목적

2장 작업의 목표는 ESS 시뮬레이터의 MQTT 경계를 문서 기준 규격으로 고정하는 것이다.

이번 작업에서는 다음을 반영했다.

- topic 규격 고정
- ESS command payload 검증
- ESS telemetry payload 직렬화
- ACK payload 직렬화
- MQTT subscriber / publisher 경계 분리
- 함수 / 조립 / 기능 테스트 추가

## 적용한 규격

### Topic

기본 topic 형식:

```text
{plant_id}/{resource_type}/{device_id}/{message_type}
```

ESS 시뮬레이터에서 사용하는 topic:

- command subscribe: `{plant_id}/ess/{device_id}/command`
- telemetry publish: `{plant_id}/ess/{device_id}/telemetry`
- ack publish: `{plant_id}/ess/{device_id}/ack`

### ESS Command

현재 반영한 command 형식:

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

현재 2장 범위에서는 `ess_mode`만 MQTT 계약으로 고정했다.

### Telemetry

현재 telemetry는 아래 구조로 직렬화된다.

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

### ACK

현재 ACK는 아래 구조로 발행된다.

```json
{
  "command_id": "cmd-042",
  "status": "accepted"
}
```

실패 시:

```json
{
  "command_id": "cmd-042",
  "status": "rejected",
  "reason": "..."
}
```

## 코드 반영 위치

- `mqtt_contract.py`
  - topic 파싱 / 생성
  - command / telemetry / ack 모델
  - snapshot → telemetry 변환
- `adapters/inbound/mqtt_subscriber.py`
  - MQTT command 검증
  - invalid payload rejected ACK 처리
- `adapters/outbound/mqtt_publisher.py`
  - telemetry / ack 직렬화 및 publish
- `core/command_handler.py`
  - 통신 모델과 분리된 내부 command 처리
- `adapters/inbound/cli_controller.py`
  - CLI도 같은 command handler 재사용

## 테스트 구조

테스트는 아래 3계층으로 정리했다.

- `tests/unit`
  - topic, payload, mapper 단위 검증
- `tests/integration`
  - subscriber / publisher 조립 검증
- `tests/functional`
  - command 수신부터 상태 반영까지 흐름 검증

전체 실행:

```bash
python -m tests
```

## 이번 작업에서 일부러 안 한 것

이번 2장에서는 아래 항목은 범위에서 제외했다.

- 실제 장비 프로토콜 연동
- Modbus / CAN / Serial 드라이버
- ESS 상태 전이 고도화
- 상세 reason code 표준화
- telemetry 추가 필드 확장

## 다음 작업 권장 순서

1. telemetry 상태 필드 확장
2. ACK / command result reason code 표준화
3. 실제 기기 입력 포트 분리
4. SOC / 상태 전이 로직 확장
