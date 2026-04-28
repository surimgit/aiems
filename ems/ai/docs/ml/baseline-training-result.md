# Baseline Solar Training Result

## Summary

The initial solar baseline training is complete.

Training environment:

```text
SSAFY shared GPU server
/home/j-k14s305/s305-work
```

Executed stages:

```text
stage 1: MLP baseline             completed
stage 2: LightGBM baseline        completed
stage 3: site correction model    skipped, no actual site data yet
```

## Model

The current production-candidate baseline is LightGBM.

LightGBM is a Microsoft open-source Gradient Boosting Decision Tree framework.
It is suitable for the current data shape because the input is tabular:

- weather features
- time features
- lag features
- rolling statistics

## Training Dataset

Files:

```text
s305-ai-data/processed/splits/solar_kpx_train.csv
s305-ai-data/processed/splits/solar_kpx_val.csv
```

Rows:

```text
train: 7271
validation: 1440
```

Target:

```text
future_solar_P_kw
```

Input features:

```text
past_solar_P_kw
past_solar_P_kw_lag_1
past_solar_P_kw_lag_24
rolling_mean_3h
rolling_mean_24h
temperature
humidity
cloud_cover
irradiance
rainfall_mm
wind_speed
hour_of_day_sin
hour_of_day_cos
day_of_year_sin
day_of_year_cos
```

## Feature Engineering Benefit

Time is transformed into cyclic features:

```text
hour_of_day_sin / hour_of_day_cos
day_of_year_sin / day_of_year_cos
```

This lets the model understand that:

- 23:00 and 00:00 are adjacent
- December and January are seasonally adjacent
- solar generation has daily and seasonal cycles

Lag and rolling features add operational history:

```text
lag_1h      recent short-term trend
lag_24h     previous-day same-time pattern
rolling_3h  short-term smoothing
rolling_24h daily baseline
```

## Result

Validation metrics after LightGBM training:

```text
MAE  = 52,539.15 W
RMSE = 80,302.48 W
```

The train target mean reported by LightGBM was about:

```text
498,926 W
```

Therefore MAE is about:

```text
52,539 / 498,926 = 10.5 percent of mean generation
```

Presentation wording:

```text
The initial LightGBM baseline reached MAE about 52.5 kW and RMSE about 80.3 kW.
Relative to the mean generation level in the training set, the MAE is about
10.5 percent.
```

## MAPE Warning

Do not use plain MAPE as the main solar metric.

Reason:

```text
actual solar generation is often zero or close to zero at night
percentage error becomes extremely large
```

Prefer:

- MAE
- RMSE
- daytime-only MAE later
- capacity-normalized MAE later
- postprocessed prediction metrics

## Postprocess Layer

The model raw output is not sent directly to EMS.

Current safety postprocess:

```text
raw_predicted_solar_kw
→ zero clamp for explicit night/low-sun signal
→ negative clamp
→ installed capacity clamp
→ predicted_solar_kw
```

The hard zero clamp uses explicit operational signals:

```text
is_daylight
solar_elevation
estimated_irradiance
target_hour
```

It does not use the current training split's raw `irradiance` column for hard
clamp because that column is normalized and may be shifted relative to the target
horizon.

## Artifact

Main artifact:

```text
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/model.joblib
```

Supporting artifacts:

```text
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/metrics.json
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/feature_importance.csv
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/validation_predictions.csv
```

