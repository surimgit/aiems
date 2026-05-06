# AI Progress Summary

## 2026-05-06 GK2A Satellite Image Training Handoff

상세 문서:

- [satellite-image-training-handoff-2026-05-06.md](./ml/satellite-image-training-handoff-2026-05-06.md)

### Data / Bundle State

- GK2A `.nc` 원본 재전처리는 현재 보류.
- 기존 위성 이미지 shard를 재사용해서 학습용 metadata를 여러 번 재패키징했다.
- 최종 비교용 로컬 zip:
  - `C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_image_anomaly_compare_regions_2025_20260506_171847.zip`
- GPU 서버 압축 해제 경로:
  - `/home/j-k14s305/s305-work/satellite_image_anomaly_compare_regions_2025_20260506_171847`
- 추가된 패키징 스크립트:
  - `ems/ai/scripts/package_satellite_daylight_bundle.py`
  - `ems/ai/scripts/package_satellite_modeling_bundle.py`
  - `ems/ai/scripts/package_satellite_anomaly_compare_bundle.py`

### Training Results

- 전체 시간 기준:
  - `tab_only` RMSE: `0.13454`
  - `image_tab_small` RMSE: `0.07276`
  - 결론: 위성 이미지는 실제로 성능에 기여한다.
- daylight 기준:
  - `daylight_v1` RMSE: `0.13542`
  - `robust_daylight_v3` RMSE: `0.13199`
- anomaly filter 비교:
  - `no_filter`: RMSE `0.13563`, MAE `0.10503`
  - `mild_filter`: RMSE `0.12674`, MAE `0.09975`
  - `strong_filter`: RMSE `0.11546`, MAE `0.09177`
- 현재 best 후보:
  - `/home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter/best_model.pt`

### Findings

- KPX 태양광 값은 실제 발전량이 아니라 판매/거래 proxy라서 낮 시간에도 이상치가 있다.
- 이상치 후보를 강하게 제거하면 daylight 성능이 개선된다.
- 현재 feature에는 풍향/풍속이 없다.
- 1h RMSE가 6h보다 나쁜 현상이 남아 있다.
  - 평가셋 구성 차이, KPX proxy 지연/왜곡, 미래 구름 이동 미모델링이 원인 후보.

### Next Session Checklist

- `strong_filter` 모델을 원본 `no_filter` validation에도 평가해서 clean-val과 real-val을 분리한다.
- horizon별 hour/region/target 분포를 확인하고, 같은 `target_timestamp_kst`만 남긴 공정 비교를 만든다.
- `metadata/horizon/strong_filter/` 기준으로 1h/2h/3h/6h 분리 모델을 학습한다.
- KMA 초단기예보 feature 병합 전처리를 만든다.
  - `UUU`, `VVV`, `VEC`, `WSD`, `SKY`, `PTY`, `RN1`, `REH`, `T1H`, `LGT`
- 다음 모델 구조로 ConvLSTM/3D CNN을 검토한다.
  - 가능하면 sequence를 `T=3`에서 `T=6`으로 늘린다.

## 2026-04-30 Branch State

- branch: `ems-ai/temp`
- remote: `origin/ems-ai/temp`
- latest commit: `2d3e77a ai_추가학습`
- working tree before docs update:
  - clean
- major additions in this branch:
  - GK2A cloud/GK2A LE2 archive collectors
  - KMA village forecast collector
  - KPX 5-minute capacity factor dataset and LightGBM model
  - RunPod inference Dockerfile and prediction smoke tests
  - operational solar forecast runner
  - model validation script

## 2026-04-30 GK2A LE2 Archive Status

- source: KMA APIHub GK2A LE2
- scripts:
  - `ems/ai/scripts/collect_gk2a_le2_archive.py`
  - `ems/ai/scripts/run_gk2a_le2_archive_monthly.py`
- config:
  - `ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml`
- target:
  - `2025-01-01 00:00+09:00 ~ 2025-12-31 23:00+09:00`
  - products: `CLA`, `CLD`
  - area: `KO`
  - expected files: `17,520`
- current collected files:
  - `7,623`
  - progress: `43.51%`
- last successful write:
  - `2026-04-30 13:53:43 KST`
- stopped intentionally:
  - `2026-04-30 14:52:54 KST`
  - active GK2A Python processes: `0`
- observed issue:
  - original network reached APIHub rate/connection failure after high-volume collection
  - NordVPN exit IPs changed public IP, but Python HTTPS failed with `SSLError: UNEXPECTED_EOF_WHILE_READING`
  - TCP 443 success alone is not sufficient; Python HTTPS single-request test must pass before restarting
- restart note:
  - `overwrite: false` allows safe resume
  - start with 1~2 parallel jobs after cooldown, then raise to 4 if stable

## 2026-04-30 KPX 5-Min Capacity Factor Model

- model: `kpx_5min_capacity_factor_lightgbm`
- artifact:
  - `ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib`
- config:
  - `ems/ai/configs/kpx_5min_capacity_factor_lightgbm.yaml`
- validation rows:
  - `2,786`
- metrics:
  - MAE: `0.0181024812`
  - RMSE: `0.0401897991`
  - clipped MAE: `0.0180349593`
  - clipped RMSE: `0.0401893899`
  - postprocessed MAE: `0.0177028470`
  - postprocessed RMSE: `0.0405369167`
- operational runner:
  - `ems/ai/scripts/run_operational_solar_forecast.py`
- RunPod inference config:
  - `ems/ai/configs/ops/operational_solar_forecast_example.yaml`

## 2026-04-30 LLM Structured Profile Flow

- script:
  - `ems/ai/scripts/structure_site_profile_with_llm.py`
- config:
  - `ems/ai/configs/ops/llm_site_profile_example.yaml`
- sample profile:
  - `ems/ai/configs/ops/site_profile_example.json`
- schema:
  - `site_profile.v1`
- purpose:
  - convert operator free text into structured profile/context features
  - save the result and reuse it during forecast cycles
- forecast integration:
  - `run_operational_solar_forecast.py` reads the saved profile
  - profile context fields are attached to RunPod payload/features
  - report LLM remains optional and disabled by default in the example config

## 2026-04-30 Load Prior Baseline

- script:
  - `ems/ai/scripts/build_load_prior.py`
- config:
  - `ems/ai/configs/ops/load_prior_example.yaml`
- inputs:
  - KEPCO city usage Excel `용도업종별`
  - KPX national hourly demand CSV
  - KASI special-day calendar
  - `site_profile.v1`
- example source:
  - `서울특별시 종로구`
  - industry: `순수써비스`
  - year: `2025`
  - month: `2025-12`
- output:
  - `ems/ai/outputs/load_prior/load_prior_example.csv`
  - `ems/ai/outputs/load_prior/load_prior_example_manifest.json`
- generated rows:
  - `48`
- predicted_load_kw summary:
  - min: `107.867334690492`
  - average: `166.605413523525`
  - max: `205.521578634804`
- safety margin:
  - reserve ratio: `15%`
  - min reserve: `10 kW`
  - output: `safe_predicted_load_kw`
- note:
  - `scale_factor` is the assumed site share of city/industry monthly usage.
  - This is a baseline/prior, not a supervised load forecast.

## 2026-04-30 Handoff Snapshot

### Current Branch / Git State

- branch: `ems-ai/temp`
- remote tracking: `origin/ems-ai/temp`
- latest committed change before this session:
  - `2d3e77a ai_추가학습`
- current working tree:
  - uncommitted AI changes exist
  - main changed areas:
    - `ems/ai/configs/ops`
    - `ems/ai/scripts`
    - `ems/ai/runpod/handler.py`
    - `ems/ai/docs`

### Added / Updated In This Session

- LLM structured profile flow:
  - `ems/ai/scripts/structure_site_profile_with_llm.py`
  - `ems/ai/configs/ops/llm_site_profile_example.yaml`
  - `ems/ai/configs/ops/site_profile_example.json`
- Operational forecast profile integration:
  - `ems/ai/scripts/run_operational_solar_forecast.py`
  - `ems/ai/configs/ops/operational_solar_forecast_example.yaml`
  - `ems/ai/runpod/handler.py`
- Load prior baseline:
  - `ems/ai/scripts/build_load_prior.py`
  - `ems/ai/configs/ops/load_prior_example.yaml`
- Docs updated:
  - `docs/progress-summary.md`
  - `docs/python-scripts.md`
  - `docs/data/data-inventory.md`
  - `docs/data/data-pipeline.md`
  - `docs/ml/llm-role.md`
  - `docs/ml/load-profile-and-llm.md`
  - `docs/ml/inference-and-retraining.md`
  - `docs/ops/ai-code-map.md`

### Verified Commands

```bash
python ems/ai/scripts/structure_site_profile_with_llm.py --config ems/ai/configs/ops/llm_site_profile_example.yaml --output ems/ai/outputs/site_profiles/seoul_profile_openai_test.json
```

- result: success
- output schema: `site_profile.v1`
- OpenAI model observed: `gpt-5.4-nano`

```powershell
$env:PYTHONPATH='ems/ai'
python ems/ai/scripts/smoke_runpod_capacity_factor_local.py --model-path ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib --val-path ems/ai/data/processed/kpx_5min_capacity_factor/kpx_5min_capacity_factor_val.csv --output-path ems/ai/outputs/runpod_capacity_factor_smoke_profile_check.json --rows 4
```

- result: success
- task: `predict_capacity_factor`

```powershell
$env:PYTHONPATH='ems/ai'
python -c "import json; from pathlib import Path; import yaml; from ems.ai.scripts.run_operational_solar_forecast import build_runpod_payload; from runpod.handler import handler; cfg=yaml.safe_load(Path('ems/ai/configs/ops/operational_solar_forecast_example.yaml').read_text(encoding='utf-8')); cfg['profile']['path']='ems/ai/outputs/site_profiles/seoul_profile_openai_test.json'; payload=build_runpod_payload(cfg); payload['model_path']='ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib'; result=handler({'input': payload}); Path('ems/ai/outputs/runpod_capacity_factor_with_profile_smoke.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8'); print(json.dumps({'ok': result.get('ok'), 'rows': result.get('rows'), 'has_profile': bool(result.get('structured_profile')), 'context_features': result.get('context_features'), 'first_prediction': result.get('predictions',[{}])[0]}, indent=2, ensure_ascii=False))"
```

- result: success
- first prediction:
  - `target_time`: `2025-12-01T13:00:00+09:00`
  - `predicted_generation_kw`: `4419.800799002141`
  - profile context included: yes

```bash
python ems/ai/scripts/build_load_prior.py --config ems/ai/configs/ops/load_prior_example.yaml
```

- result: success
- output:
  - `ems/ai/outputs/load_prior/load_prior_example.csv`
  - `ems/ai/outputs/load_prior/load_prior_example_manifest.json`
- rows: `48`
- `predicted_load_kw`:
  - min: `107.867334690492`
  - average: `166.605413523525`
  - max: `205.521578634804`
- `safe_predicted_load_kw` with 15% safety reserve:
  - min: `124.047434894066`
  - average: `191.596225552053`
  - max: `236.349815429024`

### Important Design Notes

- LLM is not the numeric prediction model.
- LLM converts operator/site free text into `site_profile.v1`.
- Forecast cycles should read the saved profile and use context fields.
- The current solar LightGBM model may ignore `profile_*` fields because they were not in its training `feature_columns`.
- The profile context is immediately useful for load prior and operation/risk decisions.
- `safe_predicted_load_kw` should be used for conservative EMS operation until actual load telemetry is available.

### GK2A / APIHub Current State

- GK2A archive collection is stopped.
- active GK2A Python processes: `0`
- collected `.nc`: `7,623 / 17,520`
- progress: `43.51%`
- last successful write: `2026-04-30 13:53:43 KST`
- APIHub issue:
  - original network and NordVPN attempts reached TCP 443 but Python HTTPS failed or timed out
  - observed Python error on VPN: `SSLError: UNEXPECTED_EOF_WHILE_READING`
  - do not restart bulk collection until a single Python HTTPS request succeeds

### Suggested Next Steps

1. Commit current AI changes.
   - suggested message: `feat: add LLM site profile and load prior baseline`
2. Build a combined forecast result script:
   - solar prediction
   - load prior
   - safe load
   - net power
   - risk fields
3. After network cooldown, test APIHub single Python HTTPS request from original IP.
4. Resume GK2A with 1~2 parallel jobs first, then 4 if stable.
5. After GK2A completes, implement NetCDF cloud feature extraction and retrain capacity factor model with cloud features.
6. Define backend persistence contract for:
   - `site_profile`
   - `forecast_result`
   - `load_prior`
   - `forecast_actual_log`

## 2026-04-27 KASI Special Day Collection

- source: 한국천문연구원 특일 정보 `SpcdeInfoService`
- script: `ems/ai/scripts/collect_kasi_special_days.py`
- config: `ems/ai/configs/data_sources/kasi_special_days_example.yaml`
- auth env: `KASI_SERVICE_KEY`
- collected years: `2021 ~ 2026`
- collected endpoints:
  - `/getRestDeInfo`
  - `/getHoliDeInfo`
  - `/get24DivisionsInfo`
- raw output:
  - `G:/내 드라이브/s305-ai-data/raw/calendar/kasi_special_days/YYYY/*.xml`
- metadata:
  - `G:/내 드라이브/s305-ai-data/raw/calendar/kasi_special_days/metadata/collection_manifest.jsonl`
- processed output:
  - `G:/내 드라이브/s305-ai-data/processed/calendar/korea_special_days.csv`
- processed rows: `381`
- processed columns:
  - `date`
  - `name`
  - `category`
  - `is_holiday`
  - `is_solar_term`
  - `source`
  - `endpoint`
  - `year`
  - `seq`
  - `locdate`

## Nationwide Expansion Note

- detailed plan: `ems/ai/docs/data/nationwide-training-data-plan.md`
- 소비 prior는 전국 단위 원천 데이터가 대부분 확보된 상태다.
- 소비 쪽 다음 병목은 추가 수집보다 `kepco_city_usage`, `kepco_contract_legal_dong`, `kpx_national_demand`, `korea_special_days.csv` 정규화/join이다.
- 전국 발전 예측 학습은 아직 전남 중심 label/weather 구조라서 추가 수집이 필요하다.
- 전국 발전 예측의 핵심 추가 데이터:
  - KPX 지역별 시간별 태양광 발전량 전체 시도
  - 전국 ASOS station 또는 KMA grid 기반 weather feature
  - 지역별 station/grid 매핑 테이블
  - 가능하면 지역별 태양광 설비용량 또는 capacity metadata

## 2026-04-30 Mentor Feedback: Weather Feature Alignment

- detailed rule: `ems/ai/docs/ml/weather-feature-alignment.md`
- GK2A LE2 cloud archive is observed historical data, so it is valid for training, validation, and offline feature experiments.
- Operational solar prediction must use future-available forecast features such as KMA ultra-short `SKY/PTY/RN1/T1H/REH/WSD` and short-term `SKY/POP/PCP/PTY/TMP/REH/WSD`.
- Do not claim production quality from a model evaluated only with GK2A observed cloud features if live inference only receives KMA forecast categories.
- `SKY` is coarse cloud-state data: `1` clear, `3` mostly cloudy, `4` cloudy/overcast. The old `2` category was merged into `1` after 2019-06-04.
- Hourly remains the current baseline. 15-minute prediction is a future step after forecast ingestion, label resolution, and API stability are verified.

## Done

- KMA ASOS 수집 스크립트 작성 및 수집 완료
- `station_165 = 목포` 확인
- Google Drive 데이터 루트 구조 생성
- KPX 태양광 CSV 정규화 완료
- KPX 태양광 API 일별 수집 스크립트 작성 및 1차 수집 완료
- KMA + KPX 병합 CSV 생성 완료
- `KMA + KPX 2025` 기반 태양광 학습용 train/val split 생성 완료
- 태양광 baseline MLP 로컬 CPU smoke test 완료
- 로컬 CPU checkpoint 기반 validation 배치 추론 CSV 생성 완료
- KPX 5분 capacity factor LightGBM 학습 및 artifact 저장 완료
- RunPod inference image/config/smoke test 흐름 추가
- 운영 태양광 예측 runner 추가
- KMA 동네예보 수집 스크립트 작성
- GK2A LE2 archive 수집 스크립트 작성 및 2025년 archive 부분 수집
- GPU 학습용 config/runbook 및 G Drive training-ready package 생성 완료
- 소비 예측용 공공 데이터 원천 파일 G Drive 정리 완료
- West Power API 수집 스크립트 초안 작성
- 문서 구조 재정리 시작

## Current Training Target

- 문제: 다음 1시간 태양광 발전량 예측
- 입력: 목포 기상 + 전남 태양광 최근 이력
- 출력: `future_solar_P_kw`

## Current Limitation

- 소비 예측용 실제 현장 부하 데이터가 아직 없다.
- 공공 통계 데이터는 소비 baseline/prior 용도로는 유용하지만, 시간 단위 현장 load 정답 데이터는 아니다.
- 태양광 baseline은 raw tabular feature 기반 1차 모델이므로, 일출/일몰처럼 발전량이 작은 구간의 상대오차가 크다.
- KPX 태양광 API는 개발계정 일일 요청 제한 때문에 날짜 단위로 나눠 꾸준히 수집해야 한다.

## Latest Data Collection

- 실행일: `2026-04-27`
- source: KPX regional hourly solar API
- endpoint: `PvAmountByLocHr/getPvAmountByLocHr`
- 수집 범위: `2024-06-01 ~ 2024-09-06`
- 중단 지점: `2024-09-07` 요청에서 rate limit 도달
- 특이사항: `2024-07-26`은 API 응답 row `0`
- raw output: `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/daily_raw/2024`
- daily CSV: `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/daily_csv/2024`
- monthly filtered CSV: `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/hourly_csv/2024`

## Latest Local CPU Smoke Test

- 실행일: `2026-04-27`
- 설정: `configs/solar_kpx_baseline.yaml`
- checkpoint: `checkpoints/solar_kpx_baseline/best.pt`
- validation rows: `1440`
- validation RMSE: `101042.55`
- validation MAE: `64604.63`
- clipped validation RMSE: `101017.68`
- prediction output: `outputs/solar_kpx_baseline_predictions.csv`
- 주의: 이 결과는 GPU 학습 결과가 아니라 로컬 CPU 기능 검증 결과다.

## Training Ready Package

- package: `G:/내 드라이브/s305-ai-data/artifacts/training_ready/solar_kpx_2025_baseline`
- train rows: `7271`
- validation rows: `1440`
- config: `configs/solar_kpx_baseline_gpu.yaml`
- runbook: `docs/gpu-training-runbook.md`
- GPU 서버에서는 `S305_AI_DATA_ROOT`, `S305_AI_OUTPUT_ROOT` 환경 변수를 잡고 실행한다.

## Latest Load Data Organization

- 실행일: `2026-04-27`
- 시군구별 전력사용량:
  - `G:/내 드라이브/s305-ai-data/raw/load/kepco_city_usage/downloads`
  - coverage: `2021 ~ 2025`
- 계약종별-법정동별 전력데이터:
  - `G:/내 드라이브/s305-ai-data/raw/load/kepco_contract_legal_dong/downloads/2025`
  - coverage: `2025-01 ~ 2025-12`
- 시간별 전국 전력수요량:
  - `G:/내 드라이브/s305-ai-data/raw/load/kpx_national_demand/downloads`
- 동네예보 격자 참고자료:
  - `G:/내 드라이브/s305-ai-data/raw/weather/kma_vilage_forecast/grid_reference`
- API 승인:
  - KMA 동네예보 `getUltraSrtNcst`, `getUltraSrtFcst`, `getVilageFcst`
  - KMA 위경도 -> 격자 변환 `nph-dfs_xy_lonlat`
  - 한국천문연구원 특일 정보 `SpcdeInfoService`
- manifest:
  - `G:/내 드라이브/s305-ai-data/raw/load/metadata/load_data_inventory_manifest.json`
- 소비 예측 방향:
  - 1차는 통계 기반 hourly load prior
  - 실제 현장 `load_kw`가 쌓이면 supervised load forecast로 확장

## Next

- 오프라인 백테스트 흐름 정리
- KPX 태양광 API `2024-09-07`부터 이어서 수집
- 소비 데이터 정규화 스크립트 작성
- KMA 동네예보 API 운영 수집 결과 검증
- KMA 초단기/단기예보 `SKY/PTY/POP/PCP/TMP/REH/WSD` 기반 forecast-compatible feature table 작성
- GK2A LE2 archive 수집 재개 및 완료
- GK2A NetCDF에서 학습용 cloud feature 추출 스크립트 작성
- GK2A observed cloud feature와 KMA forecast `SKY` 간 mismatch/정렬 실험 분리
- 한국천문연구원 특일 정보를 load prior에 join
- 소비 예측에 필요한 현장 데이터 스키마 정의
- LLM context 입력 포맷 초안 정의
