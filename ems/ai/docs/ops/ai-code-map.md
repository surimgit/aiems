# AI Code Map

This document maps the current `ems/ai` folder to runtime responsibilities.

## Top-Level Folders

```text
ems/ai/
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

Current packaged model folders:

```text
models/solar_kpx_lightgbm/
models/kpx_5min_capacity_factor_lightgbm/
```

`solar_kpx_lightgbm` is the hourly kW baseline. `kpx_5min_capacity_factor_lightgbm`
is the current operational candidate; it predicts capacity factor and converts
to kW with site capacity in the inference/ops layer.

## RunPod Code

```text
runpod/handler.py
```

Serverless worker entrypoint.

Supported tasks:

```text
task=train
task=predict
```

Current project direction:

- SSAFY GPU is used for initial training
- RunPod is used primarily for inference
- training task remains available for later tests

```text
runpod/Dockerfile
```

Builds the RunPod worker image.

```text
runpod/Dockerfile.inference
```

Lean inference image for packaged LightGBM inference.

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
sends it to the RunPod inference endpoint.

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

```text
scripts/audit_download_sources.py
```

Audits expected raw/processed files under the data root.

```text
scripts/collect_nasa_power_global_sites.py
```

Collects NASA POWER global weather/irradiance data for configured sites.

## Current Baseline Artifact

GPU output:

```text
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/model.joblib
```

This is the current baseline candidate model.

Current operational candidate:

```text
ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib
```

Validation metrics:

- MAE: `0.0181024812`
- RMSE: `0.0401897991`
- postprocessed MAE: `0.0177028470`
- postprocessed RMSE: `0.0405369167`

## Required Before Full Operation

- KMA forecast feature collection result verification
- GK2A NetCDF cloud feature extraction
- explicit `is_daylight` or `estimated_irradiance` for postprocess
- recent telemetry based load prior calibration
- load prior builder consumption of `site_profile.v1` context fields
- forecast_result persistence
- forecast_actual_log matching batch

