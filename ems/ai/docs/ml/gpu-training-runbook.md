# GPU Training Runbook

현재 바로 학습 가능한 baseline은 `solar_kpx_2025` train/val split을 사용한다.

## Current Satellite Image Note - 2026-05-06

GK2A 위성 이미지 직접 학습은 별도 handoff 문서를 우선 확인한다.

- [satellite-image-training-handoff-2026-05-06.md](./satellite-image-training-handoff-2026-05-06.md)

현재 GPU 서버 기준 best 후보:

```text
/home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter/best_model.pt
```

현재 최신 업로드 번들:

```text
C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_image_anomaly_compare_regions_2025_20260506_171847.zip
```

다음 작업은 `strong_filter` 모델을 원본 `no_filter` validation에도 평가하고, horizon별 모델 분리를 확인하는 것이다.

## Data Package

로컬 기준 원본 데이터 루트:

```text
G:/내 드라이브/s305-ai-data
```

GPU 서버에는 이 루트를 그대로 복사하거나 마운트한 뒤 환경 변수로 지정한다.

```bash
export S305_AI_DATA_ROOT=/data/s305-ai-data
export S305_AI_OUTPUT_ROOT=/data/s305-ai-runs
```

필수 파일:

```text
processed/features/solar_kpx_2025_hourly.csv
processed/features/solar_kpx_2025_hourly_manifest.json
processed/splits/solar_kpx_train.csv
processed/splits/solar_kpx_val.csv
```

## Environment Check

```bash
nvidia-smi
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

`torch.cuda.is_available()`가 `True`여야 GPU 학습이다.

## Train

저장소 루트에서 실행한다.

```bash
export PYTHONPATH=ems/ai
python -m train.train --config ems/ai/configs/solar_kpx_baseline_gpu.yaml
```

## Resume

```bash
export PYTHONPATH=ems/ai
python -m train.train --config ems/ai/configs/solar_kpx_baseline_gpu.yaml --resume
```

## Outputs

```text
$S305_AI_OUTPUT_ROOT/checkpoints/solar_kpx_baseline
$S305_AI_OUTPUT_ROOT/logs/solar_kpx_baseline
```

## Current Data Caveat

KPX API 추가 수집은 `2024-09-07`부터 이어받아야 한다. 현재 GPU 학습 준비 대상은 기존 `2025` split 기준 1차 baseline이다.
