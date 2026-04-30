# Weather Feature Alignment

Last updated: 2026-04-30

## Why This Exists

Solar generation prediction quality depends heavily on the quality and timing of weather inputs.
The current AI work has two different weather-data roles that must not be mixed:

- `GK2A LE2` cloud archive: past observation data. Use this for training, ablation, validation, and feature-quality checks.
- `KMA forecast` data: future-available data. Use this for real operational forecasting.

The important risk is training-serving mismatch. If the model is trained mainly with precise observed cloud features from GK2A, but the production forecast only receives coarse KMA forecast categories, live prediction quality can degrade even when offline training metrics look good.

## Mentor Feedback Reflected

Yeojoon mentor's main point was:

- Training parameters and prediction parameters should come from compatible sources.
- Weather forecast quality can dominate solar prediction quality.
- Solar elevation or clear-sky irradiance features alone are weak under overcast conditions.
- Industry systems often operate around 15-minute forecast intervals.

This document turns that feedback into the current implementation direction.

## Current Direction

Use GK2A LE2 as an archive/training enhancement source, not as a future forecast source.

For live prediction, prefer features that are available before the target timestamp:

- KMA ultra-short forecast for short horizon, especially `SKY`, `PTY`, `RN1`, `T1H`, `REH`, `WSD`.
- KMA short-term forecast for longer horizon, especially `SKY`, `POP`, `PCP`, `PTY`, `TMP`, `REH`, `WSD`.
- Solar geometry and calendar features as deterministic baseline features.
- Site profile context from the LLM-structured `site_profile.v1`, used as contextual priors only.

`SKY` should be treated as a coarse cloud-state feature:

- `1`: clear
- `3`: mostly cloudy
- `4`: cloudy/overcast

The old `2` category was merged into `1` after 2019-06-04, so pipelines must not assume a stable four-class cloud category.

## Modeling Rule

Do not evaluate the production model only with observation-only features that cannot exist at inference time.

Recommended experiments:

1. Baseline model with deterministic time, solar geometry, and calendar features.
2. Forecast-compatible model with KMA forecast features.
3. Archive-enhanced model with GK2A LE2 observed cloud features for offline comparison.
4. Domain-alignment model that maps GK2A cloud observations into coarser forecast-like categories and compares against KMA `SKY`.

The production candidate should be selected from forecast-compatible inputs first. GK2A improvements are useful only if they can be converted into a signal available at prediction time or used to train a robust proxy.

## Resolution Policy

The immediate baseline remains hourly because the available generation label and current collection stability are hourly-oriented.

15-minute prediction remains a target direction, but it requires:

- stable forecast collection,
- generation data at 15-minute resolution or a defensible interpolation strategy,
- validation that shorter interval error does not create worse control decisions,
- API collection that does not trigger throttling or connection failures.

2-minute forecast/cloud data should not be adopted just because it is available. It is useful only if labels, inference timing, and control decisions can consume that resolution.

## Current Status

- GK2A LE2 archive collection is partially complete and currently paused because APIHub HTTPS access became unstable.
- A 1-year hourly GK2A collection is still valuable for offline weather-feature experiments.
- The operational forecast path should be extended with KMA forecast `SKY/PTY/POP/PCP/TMP/REH/WSD` before claiming production-grade cloud-aware prediction.
- The LLM profile flow is already suitable for contextual priors, but not for replacing measured or forecast weather features.

## Next Implementation Tasks

1. Add KMA ultra-short/short forecast ingestion config and raw-data inventory entries.
2. Build a forecast-feature table aligned to generation timestamps.
3. Add a training config that uses only inference-available weather features.
4. Compare forecast-compatible metrics against the current capacity-factor baseline.
5. Keep GK2A LE2 experiments separate from production candidate evaluation unless domain alignment is explicitly applied.
