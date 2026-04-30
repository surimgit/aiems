$ErrorActionPreference = "Stop"

if (-not $env:PYTHONPATH) {
  $env:PYTHONPATH = "ems/ai"
}
if (-not $env:S305_AI_DATA_ROOT) {
  $env:S305_AI_DATA_ROOT = "G:/내 드라이브/s305-ai-data"
}
if (-not $env:S305_AI_OUTPUT_ROOT) {
  $env:S305_AI_OUTPUT_ROOT = "ems/ai"
}

Write-Host "[stage-1] MLP solar KPX baseline"
python -m train.train --config ems/ai/configs/solar_kpx_baseline_gpu.yaml

Write-Host "[stage-2] LightGBM solar KPX baseline"
python -m train.lightgbm_train --config ems/ai/configs/solar_kpx_lightgbm_gpu.yaml

$correctionTrain = Join-Path $env:S305_AI_DATA_ROOT "processed/splits/solar_site_correction_train.csv"
$correctionVal = Join-Path $env:S305_AI_DATA_ROOT "processed/splits/solar_site_correction_val.csv"
if ((Test-Path $correctionTrain) -and (Test-Path $correctionVal)) {
  Write-Host "[stage-3] Site correction LightGBM"
  python -m train.site_correction_train --config ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml
} else {
  Write-Host "[stage-3] skipped: site correction train/val CSV files are not available yet."
}
