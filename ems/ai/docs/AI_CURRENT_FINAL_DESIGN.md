# EMS AI Current Design

This document is the current AI runtime design. The initial LightGBM baseline is
kept as a historical tabular baseline, while the current solar runtime candidate
is the satellite image model `satellite_wind_safe_v6`.

## Core Position

AI is prediction-only.

- AI predicts solar generation and load.
- EMS Rule Engine decides ESS, diesel, and grid control.
- LLM is used only to structure user environment descriptions.
- LLM is not used on every forecast cycle.
- LLM does not directly control devices.

## Runtime Split

```text
Training
SSAFY shared GPU
→ legacy tabular baseline: MLP / LightGBM
→ current satellite candidate: satellite_wind_safe_v6
→ model artifacts

Operation
EC2 Forecast-AI
→ KMA forecast collection
→ telemetry/history lookup
→ feature engineering / live satellite input assembly
→ RunPod predict call
→ forecast_result DB save
→ EMS response or stream publish

Control
EMS Rule Engine
→ uses prediction
→ controls ESS/diesel/grid
```

RunPod is used for inference. Initial training is performed on the SSAFY shared
GPU.

## Current Solar Runtime Candidate

The current solar runtime candidate is `satellite_wind_safe_v6`.

```text
selected model: satellite_wind_safe_v6
checkpoint: ems/ai/checkpoints/satellite_wind_safe_v6/best_model.pt
runtime inference: RunPod Serverless
runtime image: tkatnsdl1996/s305-ems-ai-inference:satellite-v6-netcdf
RunPod endpoint: social_rose_sawfish / 2vpedud72bqd09
```

Validation result:

```text
clean_strong_val RMSE 0.106228 / MAE 0.085128
real_no_filter_fair_val RMSE 0.118638 / MAE 0.092938
real_no_filter_val RMSE 0.123338 / MAE 0.096450
```

RunPod live inference with real KMA APIHub data succeeded.

```text
input_mode: gk2a_area_proxy
target: Daejeon
forecast target: 2026-05-07T16:00:00+09:00
capacity_factor: 0.1968025863
100 kW generation estimate: 19.6802586317 kW
```

Current caveat: `gk2a_area_proxy` expands GK2A area scalar data into an image
tensor. Full production alignment still needs live GK2A NetCDF 64x64 crop
extraction using `xarray` and `pyproj`.

## Forecast Cycle

The current operational target is:

- run forecast every 30 minutes
- generate a 24-hour forecast horizon
- use KMA forecast as weather input
- use recent telemetry for lag and rolling features
- store the result in EC2 forecast DB

This is not a sub-second control loop. RunPod Serverless can use `workersMin=0`
to avoid idle GPU cost. Cold start is acceptable for this forecast cycle.

## Legacy Solar Forecast Baseline

The first tabular baseline model is LightGBM, a Microsoft open-source Gradient
Boosting Decision Tree framework. It remains useful as a fallback and comparison
baseline, but it is not the current satellite runtime candidate.

Stage layout:

- Stage 1: MLP baseline, used to verify end-to-end neural training.
- Stage 2: LightGBM baseline, legacy tabular solar baseline.
- Stage 3: site correction LightGBM, activated after actual site logs exist.

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

Target:

```text
future_solar_P_kw
```

Feature engineering benefits:

- lag features represent short-term and previous-day generation patterns
- rolling means reduce noise and capture recent trend
- `hour_of_day_sin/cos` models daily periodicity
- `day_of_year_sin/cos` models seasonal periodicity

## Current Training Result

GPU training completed successfully on the SSAFY GPU server.

```text
train rows: 7271
validation rows: 1440
MAE:  52,539.15 W
RMSE: 80,302.48 W
```

The LightGBM training log reported the train target mean around:

```text
498,926 W
```

So MAE is about:

```text
52,539 / 498,926 = about 10.5 percent of the mean generation
```

Presentation wording:

```text
The initial LightGBM baseline reached MAE about 52.5 kW and RMSE about 80.3 kW.
Relative to the mean generation level in the training set, MAE is about 10.5%.
```

Do not present plain MAPE as the main score. Solar MAPE explodes when actual
generation is zero or close to zero at night or near sunrise/sunset.

## Solar Safety Postprocess

EMS must not use raw model output directly.

```text
raw_predicted_solar_kw
→ night/low-sun zero clamp
→ negative clamp
→ installed capacity clamp
→ predicted_solar_kw
```

Rules:

- if `is_daylight = 0`, final solar prediction is zero
- if `solar_elevation <= 0`, final solar prediction is zero
- if `estimated_irradiance <= threshold`, final solar prediction is zero
- if `target_hour < 6 or target_hour > 19`, final solar prediction is zero
- if raw prediction is negative, final solar prediction is zero
- if raw prediction exceeds installed capacity, final prediction is capped

Important caveat:

The current training split has a raw `irradiance` feature in a normalized scale.
That column is not used for hard safety clamp. Operation must provide an
explicit safety signal such as:

```text
is_daylight
solar_elevation
estimated_irradiance
target_hour
installed_capacity_kw
```

The system logs both raw and final values:

```text
raw_predicted_solar_kw
predicted_solar_kw
postprocess_reason
```

## Load Forecast

Initial load forecasting is not supervised ML.

Current initial approach:

```text
base_load_by_hour
= recent telemetry based hourly average load

predicted_load_kw[t]
= base_load_by_hour[t.hour]
× profile_weight[t]
× weather_adjustment[t]
× calendar_adjustment[t]
```

Recommended base load source order:

1. recent 7-day hourly average load
2. recent 24-hour average/load pattern
3. monthly_kwh or contract_power_kw if telemetry is not enough
4. site type default profile
5. unknown fallback

## LLM User Environment Structuring

LLM is used at site setup or profile update time, not every forecast.

LLM parses free text into structured profile data:

```json
{
  "site_type": "residential",
  "components": [
    {
      "type": "air_conditioner",
      "count": 2,
      "schedule": {
        "season": "summer",
        "hours": [21, 22, 23, 0, 1, 2],
        "usage_level": "high"
      }
    }
  ]
}
```

LLM must not directly generate final power prediction or control commands.
Numeric values come from:

- equipment catalog
- profile rule table
- recent telemetry
- weather/calendar adjustment rules

LLM output must be schema-validated and saved. Operation uses the saved profile
without calling LLM again.

## EMS Interaction

Suggested 30-minute cycle:

```text
Forecast-AI scheduler
→ fetch KMA forecast for the next 24 hours
→ read recent telemetry for solar/load lag and rolling values
→ build solar feature rows
→ call RunPod solar predict
→ build load prior from telemetry/profile/weather/calendar
→ save forecast_result
→ publish or return result to EMS
```

Recommended forecast result payload:

```json
{
  "forecast_time": "2026-04-28T16:30:00+09:00",
  "target_time": "2026-04-29T14:00:00+09:00",
  "site_id": "site_001",
  "raw_predicted_solar_kw": 82.4,
  "predicted_solar_kw": 80.0,
  "predicted_load_kw": 63.1,
  "confidence": 0.82,
  "fallback_flag": false,
  "postprocess_reason": "capacity_clamp",
  "model_version": "solar_kpx_lightgbm_v1"
}
```

## Prediction vs Actual Logging

Retraining needs actual values matched to predictions.

```text
Forecast-AI saves prediction to forecast_result
Edge/EMS sends actual telemetry through ingestion
Telemetry stores actual solar/load values
Forecast-AI batch matches forecast_result with telemetry
Forecast-AI writes forecast_actual_log
```

Required actual log fields:

```text
target_time
site_id
predicted_solar_kw
actual_solar_kw
predicted_load_kw
actual_load_kw
solar_error
load_error
model_version
postprocess_reason
```

## One-Year Retraining Strategy

Initial phase:

```text
external data + telemetry prior + profile rules
```

After enough operation data:

```text
final_solar_prediction
= region/baseline prediction × site correction model
```

Load can later move from rule prior to site-specific ML after enough actual load
history exists.

## Current Files

Key code:

```text
ems/ai/train/lightgbm_train.py
ems/ai/train/solar_postprocess.py
ems/ai/train/site_correction_train.py
ems/ai/runpod/handler.py
ems/ai/scripts/runpod_client.py
```

Key configs:

```text
ems/ai/configs/solar_kpx_lightgbm_gpu.yaml
ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml
ems/ai/configs/runpod/training_job_example.yaml
```

GPU result path:

```text
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/model.joblib
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/metrics.json
```

