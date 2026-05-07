# Satellite Image Training Handoff - 2026-05-06

## Status

GK2A `.nc` 원본을 다시 까는 전처리는 현재 필요 없다. 오늘 작업은 기존 위성 이미지 shard 위에 학습용 metadata를 다시 만든 것이다.

현재 결론:

- 위성 이미지는 실제로 도움 된다.
- KPX 태양광 값은 실제 발전량이 아니라 판매/거래 proxy라서 낮 시간에도 이상치가 있다.
- 이상치 후보를 강하게 제거한 `strong_filter`가 현재 가장 좋은 daylight 기준 모델이다.
- 풍향/풍속은 현재 데이터에 없다. 1h 성능 개선에는 KMA 초단기예보 feature 병합이 필요하다.

## Local Data / Upload Bundles

원본/전처리 데이터 루트:

```text
C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data
```

현재 GPU 서버에 새로 올릴 최종 비교용 zip:

```text
C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_image_anomaly_compare_regions_2025_20260506_171847.zip
```

GPU 서버에서 풀면 기준 경로:

```text
/home/j-k14s305/s305-work/satellite_image_anomaly_compare_regions_2025_20260506_171847
```

압축 해제 셀:

```python
from pathlib import Path
import zipfile

ZIP = Path("/home/j-k14s305/s305-work/satellite_image_anomaly_compare_regions_2025_20260506_171847.zip")
OUT = Path("/home/j-k14s305/s305-work")

with zipfile.ZipFile(ZIP, "r") as z:
    z.extractall(OUT)

DATA = OUT / "satellite_image_anomaly_compare_regions_2025_20260506_171847"
print(DATA.exists(), DATA)
```

## Scripts Added

오늘 추가한 패키징 스크립트:

```text
ems/ai/scripts/package_satellite_daylight_bundle.py
ems/ai/scripts/package_satellite_modeling_bundle.py
ems/ai/scripts/package_satellite_anomaly_compare_bundle.py
```

가장 최근/중요한 스크립트:

```text
ems/ai/scripts/package_satellite_anomaly_compare_bundle.py
```

이 스크립트는 같은 위성 이미지 shard를 재사용해서 아래 세 가지 daylight 학습 variant를 만든다.

```text
no_filter
mild_filter
strong_filter
```

## Current Training Bundle Contents

중요 파일:

```text
metadata/samples_modeling_all_v4.parquet
metadata/samples_daylight_no_filter_train.parquet
metadata/samples_daylight_no_filter_val.parquet
metadata/samples_daylight_mild_filter_train.parquet
metadata/samples_daylight_mild_filter_val.parquet
metadata/samples_daylight_strong_filter_train.parquet
metadata/samples_daylight_strong_filter_val.parquet
metadata/anomaly_compare_summary.json
metadata/horizon/no_filter/samples_h{1,2,3,6}_train.parquet
metadata/horizon/mild_filter/samples_h{1,2,3,6}_train.parquet
metadata/horizon/strong_filter/samples_h{1,2,3,6}_train.parquet
```

샘플 수:

```text
no_filter:
  train 44,662
  val    8,269

mild_filter:
  train 42,000
  val    7,877

strong_filter:
  train 39,213
  val    7,400
```

이상치 후보:

```text
mild:   3,054
strong: 6,318
```

## GPU Server Results

서버:

```text
GPU: NVIDIA H200 NVL
CUDA_VISIBLE_DEVICES=0
```

전체 시간 baseline:

```text
tab_only RMSE:        0.13454
image_tab_small RMSE: 0.07276
```

위 결과로 위성 이미지가 성능에 의미 있게 기여하는 것은 확인했다. 다만 밤 0 샘플이 포함된 지표라 실제 daylight 성능보다 낙관적이다.

Daylight 기준:

```text
daylight_v1 RMSE:        0.13542
robust_daylight_v3 RMSE: 0.13199
```

Anomaly filter 비교:

```text
no_filter      RMSE 0.13563 / MAE 0.10503
mild_filter    RMSE 0.12674 / MAE 0.09975
strong_filter  RMSE 0.11546 / MAE 0.09177
```

현재 best 후보:

```text
/home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter/best_model.pt
```

현재 best의 약점:

```text
1h RMSE: 0.12493
2h RMSE: 0.12154
3h RMSE: 0.11339
6h RMSE: 0.09726
서울 RMSE: 0.14147
```

1h가 6h보다 나쁜 것은 자연스럽지 않다. 평가셋 구성 차이, KPX proxy 지연/왜곡, 미래 구름 이동을 명시적으로 모델링하지 못한 구조가 원인 후보이다.

## Model Used Today

현재 모델은 `T=3, C=4, H=64, W=64` 위성 이미지를 `12 x 64 x 64`로 flatten해서 CNN에 넣는다.

입력 이미지:

```text
t-2h, t-1h, t
CA, CF, CT, CLD
```

표 feature:

```text
estimated_capacity_kw
solar_elevation
is_daylight
hour
day_of_year
month
hour_of_day_sin/cos
day_of_year_sin/cos
region_id
horizon_id
```

한계:

- 시간축 모델이 아니라 단순 channel stack CNN이다.
- 구름 이동 방향/속도를 명시적으로 배우지 않는다.
- 풍향/풍속/KMA 예보 feature가 없다.

## Current Data Gap

현재 위성 학습 metadata에는 풍향/풍속이 없다.

확인 결과:

```text
wind_like []
```

추가해야 할 KMA 초단기예보 feature:

```text
UUU: 동서바람성분
VVV: 남북바람성분
VEC: 풍향
WSD: 풍속
SKY: 하늘상태
PTY: 강수형태
RN1: 1시간 강수량
REH: 습도
T1H: 기온
LGT: 낙뢰
```

24h 예측용 단기예보 feature 후보:

```text
TMP
SKY
PTY
POP
PCP
REH
WSD
VEC
```

## Next Work

내일 바로 할 순서:

1. `strong_filter` 모델을 원본 `no_filter` validation에도 평가한다.
   - 목적: clean-val 성능과 real-val 성능을 분리해서 확인한다.
2. horizon별 평가셋 구성이 공정한지 확인한다.
   - horizon별 hour/region/target 분포를 비교한다.
   - 같은 `target_timestamp_kst`만 남긴 공정 비교를 만든다.
3. `metadata/horizon/strong_filter/` 기준으로 1h/2h/3h/6h 분리 모델을 학습한다.
4. KMA 과거 초단기예보 수집/merge 전처리를 만든다.
   - 학습용은 API를 반복 호출하지 말고 한 번 수집 후 parquet로 고정한다.
   - 추론용은 운영 backend/scheduler가 API를 호출하고 cache한다.
5. 다음 모델 구조를 검토한다.
   - 우선 ConvLSTM 또는 3D CNN.
   - 가능하면 전처리를 `T=6`으로 늘려 `t-5h ... t`를 입력한다.

## Notes For Operations

PyCharm notebook은 긴 학습 로그 렌더링만으로 로컬 CPU/메모리를 많이 쓴다. 긴 학습은 가능하면 서버 터미널에서 `.py`로 실행한다.

권장 형태:

```bash
nohup python train_daylight.py > runs/satellite_daylight/train.log 2>&1 &
tail -f runs/satellite_daylight/train.log
```

Jupyter/PyCharm은 상태 확인과 짧은 검증 셀에만 쓰는 쪽이 낫다.

## 2026-05-07 Data Check Update

추가 분석 스크립트:

```text
ems/ai/scripts/analyze_satellite_anomaly_bundle.py
```

분석 산출물:

```text
ems/ai/outputs/satellite_anomaly_compare_v4_data_check
```

생성 파일:

```text
variant_counts.csv
val_horizon_summary.csv
fair_horizon_counts.csv
fair_horizon_summary.csv
val_hour_horizon_counts.csv
val_region_horizon_counts.csv
mild_removed_val_rows.csv
strong_removed_val_rows.csv
summary.json
README.md
```

핵심 확인 결과:

```text
strong_filter val:
  h1 rows 2072, target_mean 0.478555, peak_hour_share 0.703185
  h2 rows 1888, target_mean 0.483667, peak_hour_share 0.668962
  h3 rows 1733, target_mean 0.458464, peak_hour_share 0.612810
  h6 rows 1707, target_mean 0.344787, peak_hour_share 0.480961
```

즉 단순 validation 기준으로는 `1h`가 `6h`보다 평균 target과 피크 시간 비중이 훨씬 높다. `1h RMSE > 6h RMSE`를 곧바로 horizon 난이도 차이로 해석하면 안 된다.

같은 `(region, target_timestamp_kst)`가 1h/2h/3h/6h를 모두 가지는 fair set도 생성했다.

```text
no_filter fair rows:      4560 / 8269
mild_filter fair rows:    4384 / 7877
strong_filter fair rows:  4112 / 7400
```

fair set에서는 horizon별 target/hour/solar 분포가 동일해진다. 모델의 horizon별 실력 비교는 이 fair set 위에서 다시 봐야 한다.

추가 서버 재평가 스크립트:

```text
ems/ai/scripts/evaluate_satellite_checkpoint_crossval.py
```

GPU 서버에서 실행 예:

```bash
python ems/ai/scripts/evaluate_satellite_checkpoint_crossval.py \
  --data-dir /home/j-k14s305/s305-work/satellite_image_anomaly_compare_regions_2025_20260506_171847 \
  --checkpoint /home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter/best_model.pt \
  --variant no_filter
```

목적:

- `strong_filter` checkpoint를 원본 `no_filter` validation에 평가한다.
- 전체 no-filter val과 fair no-filter val 지표를 동시에 만든다.
- clean-val 성능과 real-val risk를 분리한다.

## 2026-05-07 KMA ASOS Wind Data Update

KMA APIHub ASOS 시간자료를 2025년 5개 대표 지점에 대해 수집했다.

수집 스크립트:

```text
ems/ai/scripts/collect_kma_asos_hourly_regions.py
```

수집 결과:

```text
expected rows: 43,800
collected rows: 43,798
missing:
  부산시 2025-06-30 09:00
  부산시 2025-06-30 10:00
```

ASOS feature parquet:

```text
C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data\processed\weather\kma_asos_apihub\kma_asos_hourly_region_features_2025.parquet
```

위성 metadata에 ASOS wind/weather feature를 병합한 GPU 업로드 번들:

```text
C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_image_wind_compare_regions_2025_20260507_093858.zip
```

추가 패키징 스크립트:

```text
ems/ai/scripts/package_satellite_wind_bundle.py
```

번들 검증:

```text
zip size: 137.7 MB
strong_filter train rows: 39,213
strong_filter val rows: 7,400
strong_filter train wind missing rows: 12
scaled wind/weather feature nulls: 0
```

주의:

- 이 ASOS 값은 과거 관측값이다.
- 성능 실험에는 유용하지만, 실제 추론에서는 KMA 초단기/단기예보의 `UUU`, `VVV`, `VEC`, `WSD` 등을 써야 한다.

## 2026-05-07 Wind Bundle Fix

GPU 서버에서 기존 wind compare v5를 학습했을 때 결과는 아래처럼 나왔다.

```text
satellite_only_strong:
  clean_strong_val RMSE 0.115547 / MAE 0.091862
  real_no_filter_fair_val RMSE 0.134397 / MAE 0.104398
  real_no_filter_val RMSE 0.140496 / MAE 0.106672

satellite_wind_strong:
  clean_strong_val RMSE 0.251457 / MAE 0.212003
  real_no_filter_fair_val RMSE 0.265374 / MAE 0.224950
  real_no_filter_val RMSE 0.250631 / MAE 0.212769
```

이 결과는 wind feature가 나빠서라기보다 v5 입력 feature 구성 문제가 크다.

- ASOS `WD`는 도 단위가 아니라 10도 단위 방위 코드다. 예: `09`는 9도가 아니라 약 90도.
- ASOS 원문 후반부에는 텍스트 날씨/구름 필드가 있어서 공백 파싱 시 `CA_TOT`, `SS`, `SI`, `VS` 같은 후반 컬럼이 밀릴 수 있다.
- 실제 확인 결과 `SS` 최대값이 5000으로 visibility처럼 보이고, `CA_TOT` 최대값이 19160201로 물리적으로 불가능했다.

그래서 v5 zip은 학습 기준으로 폐기하고, 안전 컬럼만 쓰는 v6 번들을 새로 만들었다.

```text
C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_image_wind_safe_regions_2025_20260507_095435.zip
```

v6 안전 feature:

```text
wind_u_scaled
wind_v_scaled
wind_speed_scaled
wind_dir_sin
wind_dir_cos
asos_ta_scaled
asos_hm_scaled
asos_rn_log1p
```

제외한 ASOS 컬럼:

```text
CA_TOT
CA_MID
SS
SI
VS
```

다음 실험은 v6 zip으로 `satellite_only_strong` vs `satellite_wind_safe_strong`를 다시 비교한다.

## 2026-05-07 Upwind + Visibility Bundle v7

v6 결과:

```text
real_no_filter_val
satellite_only_strong      RMSE 0.142950 / MAE 0.111731
satellite_wind_safe_strong RMSE 0.123338 / MAE 0.096450
```

v6는 `WD`/`WS`를 단순 tabular feature로만 썼다. v7은 풍속/풍향을 구름 이동 방향에 직접 쓰기 위해, 현재 위성 patch 내부에서 target 지역의 upwind 방향 영역을 계산해 cloud feature를 추가한다.

새 패키징 스크립트:

```text
ems/ai/scripts/package_satellite_upwind_visibility_bundle.py
```

업로드 대상 zip:

```text
C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_image_upwind_visibility_regions_2025_20260507_105925.zip
```

v7 추가 feature:

```text
asos_vs_scaled
asos_low_visibility_flag
asos_very_low_visibility_flag
asos_fog_or_mist_flag
asos_haze_code_flag
upwind_distance_scaled
upwind_edge_clipped
upwind_ca_scaled
upwind_cf_scaled
upwind_cld_scaled
upwind_cld_ge2_frac
upwind_missing_frac
upwind_center_cf_diff
upwind_center_cld_diff
```

검증:

```text
strong_filter train rows: 39,213
strong_filter val rows: 7,400
missing model feature values: 0
strong_filter fog_or_mist rows: 3,502
strong_filter very low visibility rows: 3,005
strong_filter upwind edge clipped rows: 93
zip size: 141.63 MB
```

ASOS 파서 수정:

- `collect_kma_asos_hourly_regions.py`의 ASOS 컬럼 순서를 수정했다.
- 원문에서 `RN_JUN`은 `RN_DAY`와 `RN_INT` 사이에 있다.
- 이 수정 후 `VS`는 10~5000m 범위로 정상 복구된다.

AirKorea PM10/PM2.5:

- `getMsrstnAcctoRltmMesureDnsty` 호출은 `DATA_DECODING` 또는 `unquote(DATA_ENCODING)`로 성공했다.
- 다만 `dataTerm=3MONTH`는 현재 기준 최근 3개월만 반환한다.
- 2025 전체 학습 feature에서는 제외하고, 운영 추론 시점 보조 feature로만 남긴다.

## 2026-05-07 Satellite v6 RunPod Live Inference

v7 `upwind + visibility` 실험 결과는 v6보다 나빴다.

```text
v7 summary:
satellite_wind_safe_strong:
  clean_strong_val RMSE 0.109245 / MAE 0.090021
  real_no_filter_fair_val RMSE 0.129351 / MAE 0.102785
  real_no_filter_val RMSE 0.132971 / MAE 0.105736

satellite_upwind_visibility_strong:
  clean_strong_val RMSE 0.119424 / MAE 0.097367
  real_no_filter_fair_val RMSE 0.146103 / MAE 0.117949
  real_no_filter_val RMSE 0.142217 / MAE 0.113110
```

따라서 현재 운영 후보는 v6 `satellite_wind_safe_strong`이다.

v6 최종 기준:

```text
clean_strong_val:
  RMSE 0.106228
  MAE  0.085128

real_no_filter_fair_val:
  RMSE 0.118638
  MAE  0.092938

real_no_filter_val:
  RMSE 0.123338
  MAE  0.096450
```

운영 해석:

- capacity factor 기준 평균 절대 오차는 대략 `0.09 ~ 0.10`이다.
- 100 kW 설비 기준 평균 절대 오차는 대략 `9 ~ 10 kW` 수준이다.
- KPX label은 판매/거래 데이터 성격이 있으므로, 사이트 실측 발전량 로그가 쌓이면 site correction이 필요하다.

선택한 checkpoint:

```text
ems/ai/checkpoints/satellite_wind_safe_v6/best_model.pt
```

RunPod 배포:

```text
image: tkatnsdl1996/s305-ems-ai-inference:satellite-v6-netcdf
digest: sha256:3816bc9ae78abda2e054953860df27210525674d8215b530a696521c5265a010
endpoint name: social_rose_sawfish
endpoint id: 2vpedud72bqd09
gpu tested: NVIDIA GeForce RTX 4090
```

RunPod에서 실제 KMA APIHub live 호출 기반 추론까지 성공했다.

```text
task: predict_live_satellite_capacity_factor
input_mode: gk2a_area_proxy
target: Daejeon
target_time_kst: 2026-05-07T16:00:00+09:00
horizon_hours: 1
installed_capacity_kw: 100

capacity_factor: 0.1968025863
predicted_generation_kw: 19.6802586317
```

사용된 forecast/API 값:

```text
T1H: 21
REH: 50
RN1: 0
SKY: 3
PTY: 0
VEC: 269
WSD: 5
```

주의:

- 현재 live 위성 입력은 `gk2a_area_proxy`이다.
- GK2A area scalar를 `(3, 4, 64, 64)` 형태로 확장해서 넣는다.
- 학습과 완전히 같은 live 입력을 만들려면 KMA APIHub live GK2A NetCDF를 받아 사용자 위치 주변 64x64 patch를 crop해야 한다.

상세 운영 문서:

```text
ems/ai/docs/ops/satellite-v6-runpod-live-inference-2026-05-07.md
```
