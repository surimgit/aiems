#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-ems/ai}"
export S305_AI_DATA_ROOT="${S305_AI_DATA_ROOT:-/data/s305-ai-data}"
export S305_AI_OUTPUT_ROOT="${S305_AI_OUTPUT_ROOT:-/data/s305-ai-runs}"

echo "[stage-1] MLP solar KPX baseline"
python -m train.train --config ems/ai/configs/solar_kpx_baseline_gpu.yaml

echo "[stage-2] LightGBM solar KPX baseline"
python -m train.lightgbm_train --config ems/ai/configs/solar_kpx_lightgbm_gpu.yaml

echo "[stage-3] Site correction LightGBM"
if [[ -f "${S305_AI_DATA_ROOT}/processed/splits/solar_site_correction_train.csv" && \
      -f "${S305_AI_DATA_ROOT}/processed/splits/solar_site_correction_val.csv" ]]; then
  python -m train.site_correction_train --config ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml
else
  echo "[stage-3] skipped: site correction train/val CSV files are not available yet."
fi
