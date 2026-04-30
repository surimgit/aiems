# ESS 충방전 및 SOC 계산 로직 적용

## 목적

이 문서는 ESS 시뮬레이터에 충방전 및 SOC 계산 로직을 반영한 결과를 정리한다.

대상 Jira:

- `S14P31S305-201 ESS 충방전 및 SOC 계산 로직 구현`

## 이번 작업에서 반영한 내용

1. `capacity_kwh` 설정 추가
2. SOC 계산식을 `전력 x 시간 / 배터리 용량` 기준으로 변경
3. 계산 함수를 작은 단위로 분리
4. SOC 경계값 clamp 반영
5. 계산 로직 단위 테스트 추가

## 계산 모델

현재 ESS 계산은 아래 순서로 진행된다.

1. `power_kw` 와 `interval_sec` 으로 이동 에너지량 계산
2. 이동 에너지량을 `capacity_kwh` 로 나누어 SOC 변화율 계산
3. 충전이면 더하고 방전이면 뺀다
4. 최종 SOC는 `0~100` 범위로 clamp 한다

공식:

- `energy_delta_kwh = abs(power_kw) * (interval_sec / 3600)`
- `soc_delta = (energy_delta_kwh / capacity_kwh) * 100`

## 코드 반영 위치

### `core/calculations.py`

추가/정리한 함수:

- `calculate_interval_hours()`
- `calculate_energy_delta_kwh()`
- `calculate_soc_delta()`
- `apply_soc_delta()`
- `clamp_soc()`
- `calculate_energy_increment()`

### `core/ess.py`

변경 내용:

- `DeviceSpec` 에 `capacity_kwh` 추가
- `tick()` 에서 `capacity_kwh` 유효성 검사 추가
- `_advance_soc()` 를 용량 기반 계산식으로 변경
- snapshot 에 `capacity_kwh` 포함
- `update_device_spec()` 로 `capacity_kwh` 변경 가능

### `runtime_config.py` / `config/devices.yaml`

변경 내용:

- 런타임 설정에 `capacity_kwh` 추가
- 기본 설정값으로 `500.0 kWh` 반영

## 현재 설정 항목

- `power_limit_kw`
- `capacity_kwh`
- `initial_soc`
- `publish_interval_sec`
- 안전 임계값들

`power_limit_kw` 는 순간 충방전 출력 제한이고,
`capacity_kwh` 는 SOC 계산에 쓰는 배터리 총 용량이다.

## 테스트 반영

### `tests/unit/test_calculations.py`

검증 범위:

- 초 -> 시간 변환
- 에너지량 계산
- 용량 기반 SOC 변화율 계산
- 충전/방전/대기별 SOC 반영
- SOC clamp
- ESS 부호 규칙

### `tests/unit/test_ess_state_logic.py`

추가 검증:

- 용량 기반 SOC 증가량 반영
- `capacity_kwh` 설정 변경 반영

### 실행 명령

```bash
python -m unittest tests.unit.test_calculations tests.unit.test_state_machine tests.unit.test_ess_state_logic tests.functional.test_ess_mqtt_flow tests.integration.test_mqtt_subscriber tests.integration.test_mqtt_publisher tests.unit.test_mqtt_contract
```

## 요약

이번 작업으로 SOC 계산이 `power_limit_kw` 기반 단순 비율 모델에서
`capacity_kwh` 기반 에너지 모델로 바뀌었다.

이제 다음 단계에서는 효율, 실제 장비 스펙, telemetry 정합성 같은 고도화 작업을 이어갈 수 있다.
