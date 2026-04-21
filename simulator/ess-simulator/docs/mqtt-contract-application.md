# ESS MQTT 계약 적용 결과

## 목적

이 문서는 ESS 시뮬레이터에 MQTT 계약을 적용한 결과를 정리한다.
기준 문서는 다음과 같다.

- `05-data-contracts/mqtt-contract.md`
- `05-data-contracts/message-schema.md`
- `08-domain-detail/telemetry-payload.md`

## 적용 범위

- 표준 MQTT topic 조립
- heartbeat topic 조립
- ESS command payload 검증
- ESS telemetry payload 직렬화
- ACK payload 직렬화
- heartbeat payload 직렬화
- MQTT subscriber / publisher 연결
- snapshot -> telemetry 변환
- 주기 발행 cycle 조립 함수 분리

## Topic

공통 topic 형식:

```text
{plant_id}/{resource_type}/{device_id}/{message_type}
```

ESS 시뮬레이터에서 사용하는 topic:

- command subscribe: `{plant_id}/ess/{device_id}/command`
- telemetry publish: `{plant_id}/ess/{device_id}/telemetry`
- ack publish: `{plant_id}/ess/{device_id}/ack`
- heartbeat publish: `{plant_id}/heartbeat`

## ESS Command

ESS MQTT 명령은 `ess_mode` 타입을 사용한다.

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

적용 규칙:

- `mode` 는 `charge`, `discharge`, `standby`만 허용
- `target_power_kw` 는 0 이상
- 잘못된 payload는 rejected ACK로 응답

## Telemetry

ESS telemetry는 아래 구조를 따른다.

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

적용 규칙:

- `timestamp` 는 UTC ISO 8601 `Z` 형식
- ESS `P`는 방전 양수, 충전 음수 규칙 유지
- telemetry 는 `snapshot_to_telemetry()`에서 조립

## ACK

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

topic:

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

## Publish Interval

S305 `Edge_Simulator_System.md` 기준에 맞춰 ESS 시뮬레이터의 기본 telemetry/heartbeat 발행 주기는 `0.1초`로 설정한다.

- 기본값: `config/devices.yaml` -> `publish_interval_sec: 0.1`
- 실제 대기 시간: `simulator_app.py` runtime loop에서 snapshot 의 `publish_interval_sec` 사용
- 관련 검증: `tests/unit/test_calculations.py`, `tests/unit/test_ess_state_logic.py`

## 코드 구조

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
  - `build_publish_batch()` 로 payload 조립
  - `log_publish_batch()` 로 로그 출력
  - `publish_batch()` 로 MQTT 발행
  - `run_publish_cycle()` 로 한 사이클 조립 + 발행 조합

## 테스트 범위

- `tests/unit`
  - topic, payload, mapper 검증
  - publish cycle 조립 함수 검증 (`test_simulator_app.py`)
- `tests/integration`
  - subscriber / publisher 검증
- `tests/functional`
  - command 수신부터 ACK와 simulator 상태 반영까지 검증

실행:

```bash
python -m unittest tests.unit.test_simulator_app tests.unit.test_calculations tests.unit.test_ess_state_logic tests.unit.test_mqtt_contract tests.integration.test_mqtt_publisher tests.integration.test_mqtt_subscriber tests.functional.test_ess_mqtt_flow
```

## 남은 범위

- command result 메시지
- reason code 고도화
- 추가 상태 필드 고도화
