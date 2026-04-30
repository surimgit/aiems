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
scripts/collect_nasa_power_global_sites.py
```

Collects NASA POWER global weather/irradiance data for configured sites.

## Current Baseline Artifact

GPU output:

```text
/home/j-k14s305/s305-work/runs/artifacts/solar_kpx_lightgbm/model.joblib
```

This is the current baseline candidate model.

## Required Before Full Operation

- Forecast-AI KMA forecast feature builder
- explicit `is_daylight` or `estimated_irradiance` for postprocess
- recent telemetry based load prior builder
- LLM structured profile parser
- forecast_result persistence
- forecast_actual_log matching batch

