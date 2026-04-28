# GPU Training Stages

## 목적

GPU 서버에서 AI 학습을 1차, 2차, 3차로 나눠 실행한다.

```text
1차: MLP solar baseline
2차: LightGBM solar baseline
3차: site correction model
```

## 공통 준비

GPU 서버에 코드 번들과 데이터 번들을 올린 뒤 압축을 푼다.

현재 생성된 업로드 번들:

```text
G:/내 드라이브/s305-ai-data/artifacts/gpu-bundles/ems_ai_code_training_stages_repo_layout.zip
G:/내 드라이브/s305-ai-data/artifacts/gpu-bundles/s305_ai_training_data_2025_clean_repo_layout.zip
```

권장 사용 번들은 위 두 개다.
압축을 풀면 각각 `ems/ai/...`, `s305-ai-data/processed/...` 구조가 유지된다.

권장 환경 변수:

```bash
export S305_AI_DATA_ROOT=/data/s305-ai-data
export S305_AI_OUTPUT_ROOT=/data/s305-ai-runs
export PYTHONPATH=ems/ai
```

Python 패키지:

```bash
pip install -r ems/ai/requirements-train.txt
```

PyTorch는 GPU 서버 CUDA 버전에 맞춰 별도 설치한다.

## 1차. MLP 태양광 baseline

설정:

```text
ems/ai/configs/solar_kpx_baseline_gpu.yaml
```

입력:

```text
${S305_AI_DATA_ROOT}/processed/splits/solar_kpx_train.csv
${S305_AI_DATA_ROOT}/processed/splits/solar_kpx_val.csv
```

실행:

```bash
python -m train.train --config ems/ai/configs/solar_kpx_baseline_gpu.yaml
```

출력:

```text
${S305_AI_OUTPUT_ROOT}/checkpoints/solar_kpx_baseline
${S305_AI_OUTPUT_ROOT}/logs/solar_kpx_baseline
```

목적:

- GPU 학습 파이프라인 검증
- train/val split, checkpoint, log 구조 확인
- 2차 LightGBM과 비교할 baseline 확보

## 2차. LightGBM 태양광 baseline

설정:

```text
ems/ai/configs/solar_kpx_lightgbm_gpu.yaml
```

실행:

```bash
python -m train.lightgbm_train --config ems/ai/configs/solar_kpx_lightgbm_gpu.yaml
```

출력:

```text
${S305_AI_OUTPUT_ROOT}/artifacts/solar_kpx_lightgbm/model.joblib
${S305_AI_OUTPUT_ROOT}/artifacts/solar_kpx_lightgbm/metrics.json
${S305_AI_OUTPUT_ROOT}/artifacts/solar_kpx_lightgbm/feature_importance.csv
${S305_AI_OUTPUT_ROOT}/artifacts/solar_kpx_lightgbm/validation_predictions.csv
```

목적:

- tabular feature에 강한 운영 baseline 후보 확보
- MLP와 MAE/RMSE/MAPE 비교
- feature importance 확인

## 3차. Site correction model

설정:

```text
ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml
```

입력:

```text
${S305_AI_DATA_ROOT}/processed/splits/solar_site_correction_train.csv
${S305_AI_DATA_ROOT}/processed/splits/solar_site_correction_val.csv
```

현재 이 파일은 아직 없다. 운영하면서 `forecast_actual_log`와 weather feature가 쌓이면 생성한다.

실행:

```bash
python -m train.site_correction_train --config ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml
```

학습 target:

```text
correction_ratio = actual_solar_kw / predicted_solar_kw_baseline
```

운영 적용:

```text
final_prediction =
  predicted_solar_kw_baseline * predicted_correction_ratio
```

## 전체 실행

Linux:

```bash
bash ems/ai/scripts/run_training_stages.sh
```

Windows PowerShell:

```powershell
.\ems\ai\scripts\run_training_stages.ps1
```

3차용 actual dataset이 없으면 runner가 3차를 자동 skip한다.

## 비교 기준

1차 MLP와 2차 LightGBM은 같은 train/val split으로 비교한다.

주요 지표:

```text
MAE
RMSE
MAPE
masked MAPE target >= 1kW
clipped MAE/RMSE
```

운영 baseline 후보는 validation metric이 더 좋은 모델을 champion으로 지정한다.

## 현재 부족한 것

3차를 실행하려면 운영 로그가 필요하다.

필수 컬럼:

```text
target_time or timestamp_utc
site_id
predicted_solar_kw_baseline
actual_solar_kw
ALLSKY_SFC_SW_DWN
CLRSKY_SFC_SW_DWN
T2M
RH2M
WS10M
PRECTOTCORR
clear_sky_ratio
temperature_factor
installed_capacity_kw
```
