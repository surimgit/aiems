# Satellite v10 RunPod Live Inference - 2026-05-08

This is the current RunPod live inference state for the front-end prediction
graph.

## Current Model

```text
model: satellite_wind_safe_multihorizon_24h_v10
checkpoint: ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt
checkpoint model_name: satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted
supported horizons: 1h through 24h
runtime target: RunPod Serverless
endpoint: social_rose_sawfish / 2vpedud72bqd09
image: tkatnsdl1996/s305-ems-ai-inference:satellite-v10-24h
```

`satellite_wind_safe_v6` remains the short-control champion for `1h`, `2h`,
`3h`, and `6h`. It is not the default model for the front-end 24-hour graph.

## Validation Summary

```text
clean_strong_val        MAE 0.079356 / RMSE 0.100202
real_no_filter_fair_val MAE 0.109242 / RMSE 0.140547
real_no_filter_val      MAE 0.094894 / RMSE 0.124597
```

The v10 training run was:

```text
/home/j-k14s305/s305-work/runs/satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted
```

## RunPod Image

The image includes project code and the v10 checkpoint. `.env` files are not
included in the image. Runtime secrets are injected by RunPod environment
variables.

```text
Docker Hub repo: tkatnsdl1996/s305-ems-ai-inference
tag: satellite-v10-24h
latest pushed digest after GK2A nearest-time patch:
sha256:62993e1011911d489522b2dc4e890780c85927018b7fc97e303d0e31a3edf6b8
```

Required worker env:

```text
KMA_AUTH_KEY
```

`RUNPOD_KEY` is a client-side key for calling the RunPod API and should not be
required inside the worker.

## Live GK2A Area Proxy

Current live input mode:

```text
input_mode: gk2a_area_proxy
channels: CA, CF_PROXY, CT_PROXY, CLD
image shape: (3, 4, 64, 64)
```

KMA APIHub GK2A area API can return `NO_DATA` at exact hourly timestamps even
when nearby 2-minute products exist. Runtime therefore searches each nominal
hourly frame within `±10` minutes in 2-minute steps.

Verified nearest-time replacements:

```text
nominal 202605081000 -> source 202605080958
nominal 202605081100 -> source 202605081058
nominal 202605081200 -> source 202605081200
```

Corresponding warnings:

```text
gk2a_area_nearest_used:202605081100->202605081058
gk2a_area_nearest_used:202605081000->202605080958
```

## Verified RunPod Inference

Request:

```text
task: predict_live_satellite_capacity_factor
region: 대전시
horizon_hours: 24
target_time: 2026-05-09T12:00:00+09:00
installed_capacity_kw: 100
```

Result after terminating the old warm worker and letting RunPod pull the new
image:

```text
status: COMPLETED
worker: er46y1jtx71iud
device: cuda
model_path: /app/ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt
predicted_capacity_factor: 0.8625134825706482
predicted_generation_kw: 86.25134825706482
model_version: satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted
```

## Remaining Production Gap

`gk2a_area_proxy` is an operational proxy, not a true NetCDF 64x64 live crop.
The next quality step is replacing it with live GK2A NetCDF crop input using
`xarray` and `pyproj`, then validating that live input distribution matches the
training input distribution.
