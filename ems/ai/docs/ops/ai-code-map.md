# AI Code Map

This document maps the current `ems/ai` folder to runtime responsibilities.

Related ops note:

- [gk2a-download-ops-note.md](./gk2a-download-ops-note.md): GK2A 다운로드 경로, 용량 특성, 404 처리, 재시작 운영 메모

## Top-Level Folders

```text
ems/ai/
  service/      Flask AI MSA runtime service
  models/       packaged model artifacts used by service and RunPod
  configs/      YAML configs for training, data sources, and RunPod
  docs/         AI design and runbooks
  notebooks/    manual GPU/Jupyter setup notebooks
  runpod/       RunPod Serverless worker image and handler
  scripts/      data collection, training runners, RunPod client
  train/        model training, inference, metrics, postprocess
```

Generated folders such as `data/`, `outputs/`, `logs/`, and `checkpoints/` are
not the source of truth. Large raw/processed data should live under:

```text
G:/내 드라이브/s305-ai-data
```

or later under S3/RDS according to the deployment plan.

## Flask AI Service

```text
service/app/main.py
```

Flask entrypoint for the AI MSA. It exposes:

- `GET /health`
- `GET /docs`
- `GET /api/ai/models`
- `POST /api/ai/site-profile/structure`
- `POST /api/ai/predict-solar`
- `POST /api/ai/predict-capacity-factor`
- `POST /api/ai/predict-satellite-capacity-factor`
- `POST /api/ai/predict-live-satellite-capacity-factor`
- `POST /api/ai/predict-load`
- `POST /api/ai/forecast`

MVC-style layout:

```text
service/app/controllers/    HTTP routes
service/app/services/       usecases
service/app/repositories/   model artifact loading
service/app/domain/         profile/load/postprocess helper logic
service/app/schemas/        request/response schemas
service/app/adapters/       external API/DB adapters
```

`service/` is the deployable runtime boundary. The offline scripts below remain
available for training, data collection, and batch jobs.

## Training Code

```text
train/train.py
```

MLP baseline training.

```text
train/lightgbm_train.py
```

Main stage 2 LightGBM solar baseline training. Saves:

- `model.joblib`
- `metrics.json`
- `feature_importance.csv`
- `validation_predictions.csv`

```text
train/site_correction_train.py
```

Stage 3 site correction model. This is skipped until real prediction-vs-actual
logs are available.

```text
train/solar_postprocess.py
```

Physical safety layer for solar predictions:

- night/low-sun zero clamp
- negative clamp
- capacity clamp

Current packaged model/checkpoint folders:

```text
checkpoints/satellite_wind_safe_v6/
checkpoints/satellite_wind_safe_multihorizon_24h_v10/
models/solar_kpx_lightgbm/
models/kpx_5min_capacity_factor_lightgbm/
```

`satellite_wind_safe_v6` remains the short-control champion for horizons
`1h`, `2h`, `3h`, and `6h`. `satellite_wind_safe_multihorizon_24h_v10` is the
RunPod/default graph model for direct `1h` through `24h` prediction. Both
predict capacity factor from GK2A image sequence input plus safe tabular
weather/time features and convert to kW with site capacity in the inference/ops
layer.
`solar_kpx_lightgbm` is the hourly kW baseline. `kpx_5min_capacity_factor_lightgbm`
is kept as the legacy tabular capacity-factor fallback/comparison point.

## RunPod Code

```text
runpod/handler.py
```

Serverless worker entrypoint.

Supported tasks:

```text
task=train
task=predict
task=predict_capacity_factor
task=predict_satellite_capacity_factor
task=predict_live_satellite_capacity_factor
task=runtime_check
```

Current project direction:

- SSAFY GPU is used for initial training
- RunPod is used primarily for inference
- training task remains available for later tests

```text
runpod/Dockerfile
```

Builds the RunPod worker image.

The active inference image should be rebuilt from `runpod/Dockerfile.inference`
after the v10 checkpoint is present:

```text
tkatnsdl1996/s305-ems-ai-inference:satellite-v10-24h
```

It includes the v10 checkpoint, PyTorch, KMA live API client dependencies, and
NetCDF/projection libraries needed for the next real GK2A crop step.

## Script Code

```text
scripts/run_training_stages.sh
scripts/run_training_stages.ps1
```

Runs stage 1, stage 2, and conditionally stage 3.

```text
scripts/runpod_client.py
```

Local client for:

- listing endpoints
- checking billing
- creating template/endpoint
- submitting jobs
- checking status

`task=predict` payloads do not require `data_zip_url`; training payloads still do.

```text
scripts/smoke_runpod_predict_local.py
```

Runs `runpod.handler` locally against the current LightGBM model and validation
split. It verifies that postprocessing fields such as `is_daylight`,
`latitude`, `longitude`, `timezone`, and `installed_capacity_kw` affect the final
`predicted_solar_kw`.

```text
scripts/smoke_runpod_capacity_factor_local.py
```

Runs `runpod.handler` locally against the packaged
`kpx_5min_capacity_factor_lightgbm` model.

```text
scripts/run_operational_solar_forecast.py
```

Builds an operational forecast request from site/config/history defaults and
sends it to the RunPod inference endpoint. This script currently builds the
legacy tabular capacity-factor payload. The current live satellite graph path is
exposed through the Flask endpoint and RunPod `predict_live_satellite_capacity_factor`
task using `satellite_wind_safe_multihorizon_24h_v10`, and still needs the
Forecast-AI scheduler/storage integration.

```text
scripts/structure_site_profile_with_llm.py
```

Converts operator free text into a validated `site_profile.v1` JSON document.
The operational forecast runner reads the saved profile and attaches context
features to forecast payloads.

```text
scripts/build_load_prior.py
```

Builds an hourly `predicted_load_kw` baseline from KEPCO monthly usage, KPX
national hourly demand shape, KASI calendar, weather adjustment, and
`site_profile.v1` context.

```text
scripts/validate_solar_model.py
```

Loads a saved model artifact and validation split to verify metrics and
postprocessing behavior.

```text
scripts/merge_kpx_capacity_factor_with_asos.py
scripts/prepare_kpx_5min_capacity_factor_dataset.py
```

Build the KPX 5-minute capacity factor training dataset and train/validation
splits.

```text
scripts/collect_kma_vilage_forecast.py
```

Collects KMA village forecast/current weather API data for operational weather
features.

```text
scripts/collect_gk2a_cloud.py
scripts/collect_gk2a_le2_archive.py
scripts/run_gk2a_le2_archive_monthly.py
```

Collect GK2A cloud/GK2A LE2 archive NetCDF data. The monthly runner is the
preferred way to resume long 2025 archive downloads.

Current operational caveats and restart behavior are documented in:

- [gk2a-download-ops-note.md](./gk2a-download-ops-note.md)

```text
scripts/audit_download_sources.py
```

Audits expected raw/processed files under the data root.

```text
scripts/collect_nasa_power_global_sites.py
```

Collects NASA POWER global weather/irradiance data for configured sites.

## Current Runtime Models

Satellite checkpoints:

```text
ems/ai/checkpoints/satellite_wind_safe_v6/best_model.pt
ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt
```

Runtime image/task:

```text
tkatnsdl1996/s305-ems-ai-inference:satellite-v10-24h
task=predict_live_satellite_capacity_factor
task=predict_satellite_capacity_factor
```

Current caveat:

- live satellite input is still `gk2a_area_proxy`
- full production alignment requires live GK2A NetCDF 64x64 crop input
- v6 remains the 1/2/3/6h short-control champion; v10 is the direct 1~24h graph/default model

## Legacy Baseline Artifact

Legacy capacity-factor artifact:

```text
ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib
```

Legacy validation metrics:

- MAE: `0.0181024812`
- RMSE: `0.0401897991`
- postprocessed MAE: `0.0177028470`
- postprocessed RMSE: `0.0405369167`

## Required Before Full Operation

- replace `gk2a_area_proxy` with live GK2A NetCDF 64x64 crop input
- connect EC2 Forecast-AI to RunPod v10 for direct 1~24h horizon generation
- forecast_result persistence
- forecast_actual_log matching batch
- KMA forecast feature collection result verification
- explicit `is_daylight` or `estimated_irradiance` for postprocess
- recent telemetry based load prior calibration
- load prior builder consumption of `site_profile.v1` context fields

