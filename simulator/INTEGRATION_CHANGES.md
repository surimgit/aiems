# Simulator Integration Changes

EMS 통합 테스트 환경에서 발생한 설정 변경 기록.
실제 배포 시에는 환경에 맞게 재설정 필요.

---

## simulator/docker-compose.yml

### 네트워크 통합 + MQTT 호스트 통일
- **변경**:
  1. 최상단에 `networks.ems_default.external: true` 선언
  2. solar / diesel / ess / load 서비스에 `networks: [ems_default]` 추가
  3. `mqtt-broker` 서비스의 포트 노출(`1883:1883`) 제거 — EMS `mosquitto`가 이미 1883 사용
  4. solar, diesel 서비스 `MQTT_HOST=mqtt-broker` → `MQTT_HOST=mosquitto` 변경
- **이유**: 각 시뮬레이터가 `simulator_default` 네트워크에만 속해 EMS `mosquitto`에 접근 불가.
  `docker network connect` 임시 연결은 컨테이너 재생성 시 해제되므로 compose에 영구 등록.
- **원본값**: 외부 네트워크 선언 없음, `MQTT_HOST=mqtt-broker`, 포트 `1883:1883` 노출

---

## ess-simulator

### `config/devices.docker.yaml`
- **변경**: `mqtt_broker_host: mqtt-broker` → `mqtt_broker_host: mosquitto`
- **이유**: EMS 네트워크의 MQTT 브로커 컨테이너명은 `mosquitto`.
  subscriber(명령 수신)가 `mqtt-broker`를 찾지 못해 command 구독 실패 →
  EMS 명령을 받지 못하고 ACK를 보내지 않던 원인.
- **원본값**: `mqtt_broker_host: mqtt-broker`

### `core/ess.py`, `core/command_handler.py` — EMS 제어권 플래그
- **변경**: `EssStatus`에 `ems_controlled: bool`, `ems_control_expires_at: datetime | None` 추가.
  `set_mode()` 호출 시 `ems_controlled=True`로 세팅, `expires_in_sec` 만큼 유효.
  `_apply_profile()`에서 EMS 제어 중이면 전력/모드 계산 skip — 온도 노이즈만 반영.
  만료 시 자율 운전 복귀. `command_handler.py`의 `_apply_ess_mode()`에서 `expires_in_sec` 전달.
- **이유**: `DefaultEssProfile`이 매 tick(0.5초)마다 `operating_mode`와 `power_kw`를 덮어써서
  EMS 명령을 `ACCEPTED`해도 실제 상태가 유지되지 않는 버그.
  현업 정석: EMS 명령 수신 시 프로파일이 모드를 덮어쓰지 않아야 함.
- **원본값**: `_apply_profile()`이 매 tick 무조건 모드/전력 덮어씀

---

## diesel-simulator

### `domain/device/models.py` — Status에 operating_mode 추가
- **변경**: `Status` 모델에 `operating_mode: str = "stopped"` 필드 추가
- **이유**: diesel telemetry에 `operating_mode`가 없어 EMS Redis state에 반영되지 않았음.
  EMS `_should_send()`가 diesel 현재 상태를 알 수 없어 매초 `start` 명령을 재발행하는 원인.
- **원본값**: `Status`에 `comms_health`만 존재

### `domain/device/diesel_device.py` — get_telemetry() state 반영
- **변경**: `get_telemetry()`에서 `self.data.status.operating_mode = self.state.value.lower()` 추가
- **이유**: `operating_mode` 필드를 추가해도 실제 state를 telemetry에 넣지 않으면 무의미.
  `DeviceState.RUNNING` → `"running"`, `DeviceState.OFF` → `"off"` 등으로 변환.
- **원본값**: `get_telemetry()`가 `self.data`를 그대로 반환 (state 미반영)

---

## load-simulator

### `config/devices.docker.yaml` — MQTT 호스트 변경
- **변경**: `mqtt_broker_host: mqtt-broker` → `mqtt_broker_host: mosquitto`
- **이유**: ess-simulator와 동일. EMS 네트워크 브로커명 불일치로 연결 실패.
- **원본값**: `mqtt_broker_host: mqtt-broker`

### `config/devices.docker.yaml` — load-03 활성화
- **변경**: load-03 항목 `enabled: false` → `enabled: true`
- **이유**: load-03이 비활성화 상태라 telemetry를 발행하지 않아 Redis state에 존재하지 않았음.
  EMS가 load-03을 인식하지 못해 전력 수급 계산 누락.
- **원본값**: `enabled: false`

### `domain/device/solar_device.py` — clear_curtailment 명령 처리 추가
- **변경**: `execute_command()`에 `clear_curtailment` 명령 타입 추가.
  수신 시 `curtailment_limit_kw = float('inf')`로 복구.
- **이유**: EMS `solar.py`가 잉여 전력 해소 또는 ESS 충전 가능 시점에 `clear_curtailment` 명령을 발행하는데,
  시뮬레이터에 해당 명령 처리 로직이 없어 `UNKNOWN_COMMAND_TYPE`으로 거부되던 문제.
- **원본값**: `curtailment` 명령만 처리, `clear_curtailment` 미처리

---

## load-simulator

### `core/load.py` — 로컬 과부하 fault 전환
- **변경**: `apply_measurement()`에서 측정 전력이 `rated_kw * 1.1` 초과 시
  `refresh_operating_state(has_fault=True)`를 호출해 로컬 fault 상태로 전환.
- **이유**: 기존 구현은 EMS 명령(load_shed)만 처리하고 자체 과부하 감지 로직이 없었음.
  정격 110% 초과 상황에서 장치 스스로 fault 전환하지 못하는 Edge 로컬 판단 누락.
- **원본값**: `apply_measurement()`가 `refresh_operating_state()`를 무조건 `has_fault=False`로 호출
