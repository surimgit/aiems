# Telemetry 1초 Coalescing

---

## 1. 목적

Edge simulator는 장치별 telemetry를 1초보다 짧은 주기로 보낼 수 있다.

하지만 EMS 내부 event bus인 Redis Stream에는 raw telemetry를 그대로 모두 올리지 않는다.

Ingestion은 장치별 최신 telemetry를 1초 window로 모은 뒤, window마다 장치별 1개 envelope만 `mg:sensor:data`에 발행한다.

```text
MQTT telemetry 0.1초
  -> Ingestion 장치별 1초 window
  -> latest envelope 1개 + window stats
  -> Redis Stream mg:sensor:data
  -> State Processor
  -> mg:state:result
  -> Socket.IO site_state_update
```

---

## 2. 발행 정책

| 메시지 타입 | 처리 방식 | 이유 |
| --- | --- | --- |
| `telemetry` | 장치별 1초 coalescing | 상태값 부하 감소, 화면 갱신 안정화 |
| `event` | 즉시 Redis Stream 발행 | 이벤트 지연 방지 |
| `emergency` | 즉시 Redis Stream 발행 | 긴급 상태 지연 방지 |
| `ack` | Ingestion에서 Stream 발행하지 않음 | Control이 직접 처리 |
| `heartbeat` | Redis TTL key 갱신 | 통신 상태 확인용 |

---

## 3. Edge 식별자와 위치

Ingestion은 MQTT payload에 포함된 edge 식별자와 위도/경도를 Redis envelope 상위 필드로 승격한다.

지원 필드:

```text
edge_id: edge_id, edgeId, edgeID, device_id, deviceId
latitude: latitude, lat, y
longitude: longitude, lon, lng, x
```

좌표는 top-level, `location`, `geo`, `position`, `site`, `edge`, `data`, `data.location`, `data.geo`, `data.position`에서 찾는다.

Redis Stream envelope 예:

```json
{
  "site_id": "PLANT-ALPHA",
  "edge_id": "edge-a",
  "resource_id": "ESS-1",
  "resource_type": "ESS",
  "location": {
    "latitude": 36.35,
    "longitude": 127.38
  },
  "latitude": 36.35,
  "longitude": 127.38
}
```

State Processor는 이 값을 `mg:state:result` snapshot과 Socket.IO `site_state_update`에 그대로 포함한다.

---

## 4. Coalescing 기준

window key는 다음 5개 값으로 구성한다.

```text
stream, site_id, edge_id, resource_type, resource_id
```

같은 key로 1초 안에 여러 telemetry가 들어오면 최신 envelope만 발행한다.

예:

```text
ESS-1 telemetry seq 1..10
```

Redis Stream 발행:

```text
ESS-1 latest seq 10 only
```

---

## 5. Window 통계

최신 envelope의 `payload.window`에 1초 window 통계를 함께 싣는다.

```json
{
  "payload": {
    "instantaneous": {
      "P": 20,
      "V": 390
    },
    "status": {
      "SOC": 71
    },
    "window": {
      "interval_sec": 1.0,
      "sample_count": 10,
      "started_at": "2026-05-12T07:23:00.000Z",
      "ended_at": "2026-05-12T07:23:00.900Z",
      "stats": {
        "instantaneous": {
          "P": {
            "avg": 15,
            "min": 10,
            "max": 20,
            "latest": 20,
            "count": 10
          }
        },
        "status": {
          "SOC": {
            "avg": 70.5,
            "min": 70,
            "max": 71,
            "latest": 71,
            "count": 10
          }
        }
      }
    }
  }
}
```

통계는 숫자 필드에 대해서만 계산한다. boolean, string, null 값은 통계 대상에서 제외한다.

---

## 6. Downstream 영향

State Processor는 기존처럼 `payload.instantaneous`와 `payload.status`의 latest 값을 기준으로 상태 snapshot을 계산한다.

따라서 Dashboard 상태 표시의 기준은 최신값이다.

`payload.window`는 State Snapshot의 `telemetry_window`로 보존된다. Socket.IO status bus도 snapshot 전체를 `data`에 싣기 때문에 프론트에서 필요하면 평균/최대/최소를 바로 참조할 수 있다.

Redis state cache key는 edge가 별도로 넘어오면 다음 형식을 사용한다.

```text
state:{site_id}:{edge_id}:{device_id}
```

edge가 없거나 device와 같으면 기존 호환성을 위해 다음 형식을 유지한다.

```text
state:{site_id}:{device_id}
```

---

## 7. 설정

기본 flush interval은 1초다.

```env
TELEMETRY_FLUSH_INTERVAL_SEC=1.0
```

설정 위치:

```text
ems/ingestion/app/config.py
```

구현 위치:

```text
ems/ingestion/app/adapters/telemetry_coalescer.py
ems/ingestion/app/adapters/mqtt_subscriber.py
```

---

## 8. 운영 확인

Ingestion 로그에서 1초마다 flush 요약이 보이면 정상이다.

```text
[ingestion] telemetry flush: mg:sensor:data=5
```

의미:

```text
현재 window에서 장치 5개에 대한 latest telemetry 5개를 mg:sensor:data에 발행
```

State Processor 로그와 Frontend Socket.IO `site_state_update`도 장치별 약 1초 주기로 내려와야 한다.

Socket.IO 메시지에서 다음 필드가 보이면 edge/location 전달도 정상이다.

```json
{
  "edge_id": "edge-a",
  "device_id": "ESS-1",
  "latitude": 36.35,
  "longitude": 127.38
}
```

---

## 9. 주의사항

- 이 방식은 raw 0.1초 telemetry를 보존하지 않는다.
- Redis Stream에는 1초 window의 latest envelope만 발행된다.
- 1초 window의 평균/최대/최소는 `payload.window.stats`에 포함된다.
- 같은 site 안에서 edge가 여러 개면 `edge_id`가 반드시 함께 넘어와야 coalescing/state cache가 분리된다.
- `event`와 `emergency`는 coalescing하지 않는다.
- DB writer가 0.1초 원본 기반 sensor 통계를 저장해야 한다면 별도 raw stream 또는 window stats 반영 로직이 필요하다.

---

## 10. 결론

Ingestion의 telemetry coalescing은 Redis Stream event bus의 속도를 장치별 1초 단위로 안정화한다.

State Processor와 Frontend는 edge 식별자, 위치, 최신 상태, window 통계를 1초 단위로 받을 수 있다.
