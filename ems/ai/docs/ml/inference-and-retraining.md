# Inference And Retraining

## Core Distinction

추론과 재학습은 분리된 단계다.

### Inference

- 이미 학습된 모델을 사용한다.
- 현재 입력값으로 예측값을 만든다.
- 빠르게 돌아야 한다.
- EMS 운영 경로에 주기적으로 연결된다.

예:

- 지금 날씨와 최근 발전량으로 다음 1시간 발전량 예측

현재 운영 후보:

- model: `kpx_5min_capacity_factor_lightgbm`
- artifact: `ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib`
- endpoint config: `ems/ai/configs/ops/operational_solar_forecast_example.yaml`
- runner: `ems/ai/scripts/run_operational_solar_forecast.py`
- prediction unit:
  - model raw output: capacity factor
  - operational output: `predicted_solar_kw`

운영 추론 feature 원칙:

- target timestamp 이전에 확보 가능한 입력만 사용한다.
- GK2A LE2 cloud archive는 과거 관측 자료이므로 live inference feature로 취급하지 않는다.
- 태양광 운영 예측의 weather feature는 KMA 초단기/단기예보 기반으로 구성한다.
- LLM `site_profile.v1`은 site/load context prior이며, 날씨 feature를 대체하지 않는다.

현재 batch inference 엔트리포인트:

```bash
PYTHONPATH=ems/ai python -m train.infer --config ems/ai/configs/solar_kpx_baseline.yaml --include-target-metrics
```

기본 출력:

- `outputs/solar_kpx_baseline_predictions.csv`
- `predicted_solar_P_kw`
- `predicted_solar_P_kw_clipped`

### Runtime Predict Payload

운영 추론 요청은 모델 입력 feature와 후처리 feature를 같이 보낸다.

모델은 `feature_columns`만 사용한다. 후처리 feature는 모델 재학습 대상이 아니라,
`raw_predicted_solar_kw`를 운영 가능한 `predicted_solar_kw`로 보정하는 안전 입력이다.

필수 후처리 feature:

- `target_time`
- `target_hour`
- `installed_capacity_kw`

선택 후처리 feature:

- `latitude`
- `longitude`
- `timezone`
- `is_daylight`
- `estimated_irradiance` in W/m2 scale, not the normalized training feature
- `solar_elevation`

운영 weather feature 후보:

- 초단기예보: `SKY`, `PTY`, `RN1`, `T1H`, `REH`, `WSD`
- 단기예보: `SKY`, `POP`, `PCP`, `PTY`, `TMP`, `REH`, `WSD`

`SKY`는 `1` 맑음, `3` 구름많음, `4` 흐림으로 처리한다.
과거 `2` category는 2019-06-04 이후 `1`로 병합되었으므로 현재 운영 feature에서는 별도 class로 두지 않는다.

If `solar_elevation` is not supplied, the AI worker can compute it from
`target_time`, `latitude`, `longitude`, and `timezone` with `astral`.

후처리 규칙:

- `is_daylight <= 0`: `predicted_solar_kw = 0`
- `solar_elevation <= 0`: `predicted_solar_kw = 0`
- `estimated_irradiance <= 10`: `predicted_solar_kw = 0`
- `target_hour < 6` or `target_hour > 19`: `predicted_solar_kw = 0`
- prediction < 0: `predicted_solar_kw = 0`
- prediction > `installed_capacity_kw`: `predicted_solar_kw = installed_capacity_kw`

EMS는 `raw_predicted_solar_kw`가 아니라 `predicted_solar_kw`를 사용한다.
`raw_predicted_solar_kw`와 `postprocess_reason`은 예측 로그와 재학습 검증용으로 저장한다.

Current validation note:

- `target_hour/is_daylight` postprocessing keeps overall validation error close to the raw model.
- `solar_elevation` support is implemented, but should be enabled as the default only after confirming timestamp and timezone alignment between telemetry, weather forecast, and target horizon.

### Current Capacity Factor Model Metrics

`kpx_5min_capacity_factor_lightgbm` validation:

- train rows: `16,969`
- validation rows: `2,786`
- MAE: `0.0181024812`
- RMSE: `0.0401897991`
- clipped MAE: `0.0180349593`
- clipped RMSE: `0.0401893899`
- postprocessed MAE: `0.0177028470`
- postprocessed RMSE: `0.0405369167`

This is the current operational candidate because capacity factor is easier to
reuse across sites with different installed capacities than direct kW output.

### Retraining

- 새로 쌓인 데이터를 포함해 모델을 다시 학습한다.
- 배치성 작업이다.
- 월별/분기별로 수행할 수 있다.
- 이전 모델보다 좋아질 때만 교체한다.

재학습 후보는 feature source별로 분리해서 평가한다.

- deterministic baseline: 시간, calendar, 태양고도/일사 추정 feature
- forecast-compatible model: deterministic feature + KMA forecast feature
- archive-enhanced offline model: deterministic feature + GK2A observed cloud feature
- alignment model: GK2A observed cloud를 KMA `SKY`와 비교하거나 forecast-like category로 변환한 feature

production champion 후보는 forecast-compatible model에서 선택한다.
GK2A observed cloud로만 좋아진 모델은 live inference에서 동일 feature를 공급할 수 있을 때만 운영 후보로 승격한다.

## Recommended Flow

```text
Initial training
  -> periodic inference
  -> prediction/actual log accumulation
  -> offline backtest
  -> periodic retraining candidate
  -> champion/challenger comparison
  -> promote only if improved
```

## Minimum Log To Keep

재학습과 검증을 위해 최소한 아래는 저장해야 한다.

- `timestamp`
- `predicted_generation_kw`
- `actual_generation_kw`
- `predicted_load_kw`
- `actual_load_kw`
- weather snapshot
- site state
- operator context
- model version

## Why Backtesting Matters

현재 시뮬레이터/EMS에는 시간 가속 기능이 없다.

그래서 모델 검증은 `과거 데이터 백테스트`가 기본이다.

예:

1. 특정 시점까지의 입력만 사용
2. 다음 시점 값을 예측
3. 실제값과 비교
4. 전체 기간에 대해 반복

이 방식으로:

- 모델 버전 비교
- 재학습 효과 확인
- 오차 패턴 분석

이 가능하다.

현재 validation split 기준 1차 backtest 결과:

- checkpoint: `checkpoints/solar_kpx_baseline/best.pt`
- rows: `1440`
- RMSE: `101042.55`
- MAE: `64604.63`
- clipped RMSE: `101017.68`

## Quarterly Retraining

분기 재학습은 가능하지만 자동으로 정확도가 좋아지지는 않는다.

교체 조건은 아래처럼 잡는 것이 안전하다.

1. 분기 데이터 추가
2. 새 모델 학습
3. 최근 holdout 구간에서 이전 모델과 비교
4. 더 좋을 때만 운영 모델 교체
