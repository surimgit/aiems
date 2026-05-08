# Model Strategy

## Current Runtime Models

현재 태양광 runtime은 목적별로 분리한다.

- `satellite_wind_safe_v6`
  - 단기 제어용 champion
  - 지원 horizon: `1h`, `2h`, `3h`, `6h`
- `satellite_wind_safe_multihorizon_24h_v10`
  - 프런트 예측 그래프용 1~24h multi-horizon 모델
  - checkpoint: `ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt`
  - RunPod inference 기본 satellite model path

- 입력:
  - GK2A image sequence
  - safe wind/weather feature
  - 태양고도, 시간, 설비용량 feature
- 출력:
  - capacity factor
  - `predicted_generation_kw`
- 현재 한계:
  - live input은 아직 실제 NetCDF 64x64 crop이 아니라 `gk2a_area_proxy`이다.
  - v10은 1~24h를 직접 예측하지만, 실제 운영 정확도는 live weather/GK2A 입력 품질에 의존한다.

## Legacy First Model

현재 바로 학습 가능한 모델은 `태양광 발전량 1시간 ahead 예측 모델`이다.

- 입력:
  - 최근 발전량
  - lag feature
  - rolling mean
  - 기상 feature
  - 시간 파생 feature
- 출력:
  - `future_solar_P_kw`

## Why The Legacy Model Came First

초기에는 공공데이터만으로 가장 현실적으로 만들 수 있는 모델이었기 때문이다.

- 발전 예측:
  - `KMA + KPX`만으로 baseline 가능
- 소비 예측:
  - 현재 공공 통계 데이터는 확보됨
  - 다만 시간 단위 현장 load label이 아니므로 supervised load model은 아직 이르다.
  - 1차는 통계 기반 hourly load prior로 구현한다.

## Baseline Model Type

현재 baseline 학습 코드는 `PyTorch MLP`다.

MLP를 먼저 쓰는 이유:

- 구조가 단순하다.
- 빠르게 학습/검증 가능하다.
- feature engineering 결과를 바로 시험해볼 수 있다.

이후 비교 후보:

- XGBoost / LightGBM
- LSTM / GRU
- Transformer 계열

## What Is Not A Primary Learning Target

### ESS

ESS는 1차적으로 별도 예측 모델로 학습시키지 않는다.

현재 구조:

- AI:
  - 발전 예측
  - 소비 baseline/prior
  - 이후 실제 load log 기반 소비 예측
- EMS 정책 엔진:
  - `net_power` 계산
  - SOC 계산
  - 충전/방전 판단

## Load Baseline Strategy

소비 예측은 아래 입력으로 시작한다.

- 시군구별 전력사용량 `2021 ~ 2025`
- 계약종별-법정동별 전력데이터 `2025`
- 시간별 전국 전력수요량 profile
- KMA 관측/예보 기상
- 요일/공휴일/운영자 context

1차 목표는 `predicted_load_kw`를 만드는 baseline이다.

```text
monthly usage kWh
  -> daily allocation
  -> hourly profile allocation
  -> weather/context adjustment
  -> predicted_load_kw
```

이 값은 EMS 운영 판단의 직접 제어값이 아니라 `predicted_net_power_kw = predicted_load_kw - predicted_generation_kw` 계산을 위한 보조 입력으로 둔다.

### LLM

LLM은 예측 모델 본체가 아니다.

역할:

- 사용자/운영자의 자연어 입력을 읽는다.
- 이를 구조화된 context feature로 변환한다.
- 추론 시점에 수치 모델을 보조한다.
