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
