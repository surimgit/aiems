# Satellite v6 RunPod Live Inference - 2026-05-07

이 문서는 2026-05-07 기준 EMS AI의 위성 이미지 기반 태양광 추론 상태를 정리한다.

## Current Decision

현재 운영 후보 모델은 `satellite_wind_safe_v6`이다.

v7 `upwind + visibility` 실험은 v6보다 성능이 낮았으므로 현재 운영 후보에서 제외한다.

```text
selected model: satellite_wind_safe_v6
checkpoint: ems/ai/checkpoints/satellite_wind_safe_v6/best_model.pt
runtime target: RunPod Serverless
runtime image: tkatnsdl1996/s305-ems-ai-inference:satellite-v6-netcdf
```

## Model Quality

GPU 서버 비교 결과 v6 `satellite_wind_safe_strong`가 현재 최선이다.

```text
clean_strong_val:
  MAE  0.085128
  RMSE 0.106228

real_no_filter_fair_val:
  MAE  0.092938
  RMSE 0.118638

real_no_filter_val:
  MAE  0.096450
  RMSE 0.123338
```

해석:

- capacity factor 기준 평균 오차는 대략 `0.09 ~ 0.10` 수준이다.
- 100 kW 설비라면 평균 절대 오차는 대략 `9 ~ 10 kW` 수준으로 설명할 수 있다.
- real no-filter 검증에는 KPX 판매/거래 label 이상치가 섞여 있으므로, 실서비스 기대치는 사이트 실측 로그가 쌓인 뒤 다시 보정해야 한다.

## Input Features

이미지 입력:

```text
shape: (3, 4, 64, 64)
time frames: 3
channels: CA, CF, CT, CLD
```

기본 tabular feature:

```text
cap_scaled
solar_elev_scaled
is_daylight
hour_scaled
doy_scaled
month_scaled
hour_of_day_sin
hour_of_day_cos
day_of_year_sin
day_of_year_cos
```

v6 safe wind/weather feature:

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

주의:

- v6에서 풍향/풍속은 구름 patch를 실제로 이동시키는 optical flow 방식이 아니다.
- 풍향/풍속은 tabular weather signal로 들어간다.
- v7에서 upwind cloud feature를 시도했지만 검증 성능이 떨어져 현재 폐기한다.

## RunPod Runtime

Docker image:

```text
tkatnsdl1996/s305-ems-ai-inference:satellite-v6-netcdf
digest: sha256:3816bc9ae78abda2e054953860df27210525674d8215b530a696521c5265a010
```

RunPod endpoint:

```text
endpoint name: social_rose_sawfish
endpoint id: 2vpedud72bqd09
template id: 1g9q2pe5se
gpu tested: NVIDIA GeForce RTX 4090
```

RunPod environment:

```text
required worker env: KMA_AUTH_KEY
not required in worker env: RUNPOD_KEY
```

`RUNPOD_KEY`는 클라이언트가 RunPod API를 호출할 때 쓰는 키이므로 worker template에 넣지 않는다.

## Runtime Check

RunPod `runtime_check` task 통과 상태:

```text
cuda: true
gpu: NVIDIA GeForce RTX 4090
model_exists: true
model_device: cuda
```

주요 runtime package:

```text
torch 2.5.1+cu124
numpy 2.2.5
pandas 2.2.3
xarray 2025.1.2
pyproj 3.7.0
netCDF4 1.7.2
h5netcdf 1.4.1
requests 2.32.3
runpod 1.7.9
```

## Live API Test

RunPod에서 실제 KMA APIHub 값을 호출해 live 추론에 성공했다.

```text
task: predict_live_satellite_capacity_factor
input_mode: gk2a_area_proxy
target: Daejeon
target_time_kst: 2026-05-07T16:00:00+09:00
horizon_hours: 1
installed_capacity_kw: 100
model_device: cuda
```

KMA weather values:

```text
T1H: 21
REH: 50
RN1: 0
SKY: 3
PTY: 0
VEC: 269
WSD: 5
```

Prediction result:

```text
capacity_factor: 0.1968025863
predicted_generation_kw for 100 kW: 19.6802586317
```

RunPod timing:

```text
delay: about 73.9 s
execution: about 43.9 s
client total: about 118.3 s
```

이 시간은 serverless cold start와 KMA/GK2A 외부 API 호출 시간이 포함된 값이다.

## Live API Sources

현재 live endpoint에서 호출하는 KMA APIHub 기능:

```text
nph-dfs_xy_lonlat
  - latitude/longitude -> KMA nx/ny grid conversion

nph-dfs_vsrt_grd
  - ultra-short forecast
  - T1H, REH, RN1, SKY, PTY, VEC, WSD

nph-dfs_odam_grd
  - nowcast fallback

getGk2aclaArea
  - GK2A cloud amount area data

getGk2acldArea
  - GK2A cloud detection area data
```

## Important Limitation

현재 live 위성 입력은 `gk2a_area_proxy`이다.

즉, KMA APIHub의 GK2A area scalar 값을 받아서 `(3, 4, 64, 64)` 이미지 텐서 형태로 확장한다. 학습 때 사용한 실제 지역별 64x64 NetCDF crop과 완전히 같은 입력은 아니다.

정식 고도화 단계는 아래와 같다.

1. KMA APIHub에서 live GK2A LE2 NetCDF 또는 equivalent grid file을 가져온다.
2. `xarray`, `pyproj`로 GK2A projection 좌표를 해석한다.
3. 사용자 위치 주변 64x64 patch를 crop한다.
4. CA, CF, CT, CLD 채널을 학습과 동일한 normalization으로 구성한다.
5. 현재 `gk2a_area_proxy`를 real patch input으로 교체한다.

## Flask / RunPod Tasks

로컬 Flask endpoint:

```text
POST /api/ai/predict-satellite-capacity-factor
POST /api/ai/predict-live-satellite-capacity-factor
```

RunPod handler tasks:

```text
runtime_check
predict_live_satellite_capacity_factor
```

## Code State

관련 코드:

```text
ems/ai/inference/satellite_wind_safe.py
ems/ai/service/app/services/live_satellite_service.py
ems/ai/service/app/controllers/prediction_controller.py
ems/ai/service/app/schemas/prediction_schema.py
ems/ai/runpod/handler.py
```

관련 dependency 파일:

```text
ems/ai/requirements-runpod-inference.txt
ems/ai/service/requirements.txt
ems/ai/requirements-train.txt
```

추가된 NetCDF/projection dependency:

```text
xarray==2025.1.2
pyproj==3.7.0
netCDF4==1.7.2
h5netcdf==1.4.1
```

## Current Operation Summary

현재 상태는 “모델 학습 및 RunPod 실시간 API 연동 proof 단계 완료”이다.

완료:

- v6 모델 선택
- RunPod Docker image push
- RunPod 4090 endpoint runtime check
- 실제 KMA APIHub 호출 기반 live 추론 성공
- Flask/RunPod handler에 live endpoint 연결

남은 정식화:

- `gk2a_area_proxy`를 live NetCDF 64x64 crop으로 교체
- 24시간 horizon을 여러 시간 target으로 반복 호출하는 orchestration 추가
- EC2 Forecast-AI에서 RunPod endpoint 호출 및 DB 저장 연결
- 사이트 실측 발전량 로그 기반 site correction/retraining 설계
