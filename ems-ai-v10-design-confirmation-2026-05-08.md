# EMS AI v10 설계 확인 문서

작성일: 2026-05-08  
대상: EMS 태양광 발전량 예측 AI 설계 검토/컨펌용  
문서 목적: 사람이 빠르게 훑거나, 다른 AI가 이 파일 하나만 읽고 현재 AI 설계/학습/추론/배포 상태를 이해할 수 있도록 전체 맥락과 세부 구현을 같이 정리한다.

---

## 1. 최종 결론

현재 운영 기준 모델은 `satellite_wind_safe_multihorizon_24h_v10`이다.

내부 체크포인트의 실제 학습 모델명은 `satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted`이며, 위성 기반 CNN과 수치 피처 MLP를 결합한 1~24시간 다중 horizon 예측 모델이다.

프론트 예측 그래프는 기본적으로 이 v10 모델을 기준으로 1시간부터 24시간까지 값을 채우는 설계다. 과거 논의에서 v6는 1h, 2h, 3h, 6h 단기 제어용 강점 모델로 남겨두는 방향이었고, LightGBM은 현재 graph 기본 fallback이 아니라 legacy tabular baseline/challenger로 보는 것이 맞다.

운영 추론은 RunPod Serverless에서 Docker 이미지로 수행한다.

- Docker Hub 이미지: `tkatnsdl1996/s305-ems-ai-inference:satellite-v10-24h`
- RunPod endpoint: `social_rose_sawfish / 2vpedud72bqd09`
- 운영 체크포인트 경로: `/app/ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt`
- 로컬 체크포인트 경로: `C:\Users\SSAFY\PycharmProjects\S14P31S305\ems\ai\checkpoints\satellite_wind_safe_multihorizon_24h_v10\best_model.pt`

---

## 2. 모델이 예측하는 값

모델의 직접 출력은 태양광 설비용량 대비 발전 비율인 `capacity factor`다.

서비스 응답에서는 이 값을 요청 설비용량에 곱해서 `predicted_generation_kw`도 같이 제공한다.

```text
predicted_capacity_factor = model_output
predicted_generation_kw = predicted_capacity_factor * installed_capacity_kw
```

예를 들어 `installed_capacity_kw = 100`이고 모델 출력이 `0.8625`이면 예상 발전량은 약 `86.25 kW`다.

주의할 점은 학습 target이 순수 물리 계측 발전량이 아니라 KPX 거래량/실적 기반 proxy라는 점이다. 그래서 일부 최악 오차 사례는 태양 위치나 구름만으로 설명되지 않고, 거래/정산/집계 구조에서 생기는 왜곡일 가능성이 크다.

---

## 3. 지원 범위

### 3.1 지역

운영 모델은 다음 5개 지역을 지원한다.

| 지역 | region id | 대표 좌표 | KMA dongCode |
|---|---:|---|---|
| 대전시 | 0 | 36.3504, 127.3845 | 3000000000 |
| 부산시 | 1 | 35.1796, 129.0756 | 2600000000 |
| 서울시 | 2 | 37.5665, 126.9780 | 1100000000 |
| 울산시 | 3 | 35.5384, 129.3114 | 3100000000 |
| 제주도 | 4 | 33.4996, 126.5312 | 5000000000 |

### 3.2 예측 horizon

지원 horizon은 1시간부터 24시간까지다.

```text
horizon_hours: 1, 2, 3, ..., 24
horizon_id: horizon_hours - 1
```

단일 요청으로 특정 horizon 하나를 예측할 수도 있고, 프론트/제어 서비스에서 1~24를 반복 호출해서 하루 그래프를 구성할 수도 있다.

---

## 4. 모델 구조

모델 클래스는 학습 노트북 기준 `SatelliteSolarModel`이다.

전체 구조는 다음과 같다.

```text
입력
  - 위성/구름 이미지 텐서: 12 x 64 x 64
  - 수치 피처 벡터: 기상, 태양 위치, 시간, horizon context
  - region id embedding
  - horizon id embedding

모델
  - CNN image branch
  - tabular MLP branch
  - region/horizon embedding
  - short head: 1h~6h
  - long head: 7h~24h

출력
  - predicted_capacity_factor
```

### 4.1 CNN image branch

위성/구름 입력은 12채널 이미지로 들어간다.

```text
Conv2d(12, 48, kernel=3, padding=1)
BatchNorm2d(48)
SiLU
MaxPool2d(2)

Conv2d(48, 96, kernel=3, padding=1)
BatchNorm2d(96)
SiLU
MaxPool2d(2)

Conv2d(96, 192, kernel=3, padding=1)
BatchNorm2d(192)
SiLU
AdaptiveAvgPool2d(1)
```

CNN 결과는 192차원 image feature로 압축된다.

### 4.2 Embedding

```text
region embedding: 5 regions -> 8 dimensions
horizon embedding: 24 horizons -> 8 dimensions
```

### 4.3 Tabular branch

수치 피처와 embedding을 합쳐 tabular branch에 넣는다.

```text
Linear(num_dim + 16, 128)
SiLU
Linear(128, 128)
SiLU
```

### 4.4 Prediction heads

최종 feature는 `image_feat(192) + tab_feat(128) = 320` 차원이다.

short head:

```text
Linear(320, 128)
SiLU
Dropout(0.1)
Linear(128, 1)
```

long head:

```text
Linear(320, 128)
SiLU
Dropout(0.15)
Linear(128, 1)
```

head 선택 정책:

```text
1h~6h   -> short_head
7h~24h  -> long_head
```

코드 내부에서는 horizon id가 0부터 시작하므로 `horizon >= 6`일 때 long head가 선택된다.

---

## 5. 수치 피처 목록

학습/추론에서 쓰는 수치 피처는 크게 기본 태양/시간 피처, 풍향/풍속 안전 피처, horizon context 피처로 나뉜다.

### 5.1 기본 태양/시간 피처

| 피처 | 의미 | 생성 방식 |
|---|---|---|
| `cap_scaled` | 모델 입력용 기준 설비용량 scale | `capacity_kw / 300000.0` |
| `solar_elev_scaled` | 태양 고도 scale | `solar_elevation / 90.0` |
| `is_daylight` | 주간 여부 | 태양 고도 기준 daylight flag |
| `hour_scaled` | 대상 시각의 hour scale | `hour / 23.0` |
| `doy_scaled` | day-of-year scale | `day_of_year / 366.0` |
| `month_scaled` | month scale | `month / 12.0` |
| `hour_of_day_sin` | hour 주기 sin | `sin(2*pi*hour/24)` |
| `hour_of_day_cos` | hour 주기 cos | `cos(2*pi*hour/24)` |
| `day_of_year_sin` | 연중 일자 주기 sin | `sin(2*pi*doy/366)` |
| `day_of_year_cos` | 연중 일자 주기 cos | `cos(2*pi*doy/366)` |

태양 고도 계산에는 Python `astral` 계열 계산을 사용한다. 이 피처가 들어가면서 단순 거래량 proxy의 한계를 줄이고, 같은 시간대라도 계절/입사각 차이를 모델이 구분할 수 있게 했다.

### 5.2 풍향/풍속/기상 안전 피처

| 피처 | 의미 | 생성 방식 또는 원천 |
|---|---|---|
| `wind_u_scaled` | 풍속 U 성분 | `wind_speed * sin(wind_dir) / 15.0` |
| `wind_v_scaled` | 풍속 V 성분 | `wind_speed * cos(wind_dir) / 15.0` |
| `wind_speed_scaled` | 풍속 scale | `wind_speed_ms / 15.0` |
| `wind_dir_sin` | 풍향 sin | 풍향 degree -> radian -> sin |
| `wind_dir_cos` | 풍향 cos | 풍향 degree -> radian -> cos |
| `asos_ta_scaled` | 기온 scale | `(temperature_c + 30.0) / 70.0` |
| `asos_hm_scaled` | 습도 scale | `humidity_pct / 100.0` |
| `asos_rn_log1p` | 강수량 log scale | `log1p(max(0, rainfall_mm))` |

운영 추론에서는 기상청 초단기 예보/실황에서 다음 값을 사용한다.

| 원천 category | 사용 의미 |
|---|---|
| `T1H` 또는 `TMP` | 기온 |
| `RN1` 또는 `PCP` | 강수량 |
| `VEC` | 풍향 |
| `WSD` | 풍속 |
| `REH` | 습도 |
| `SKY` | 하늘 상태, 구름 proxy 보정 |
| `PTY` | 강수 형태 |

### 5.3 Horizon context 피처

| 피처 | 의미 | 생성 방식 |
|---|---|---|
| `horizon_hours_scaled` | horizon scale | `(horizon_hours - 1) / 23.0` |
| `horizon_hours_sin` | horizon 주기 sin | `sin(2*pi*horizon_hours/24)` |
| `horizon_hours_cos` | horizon 주기 cos | `cos(2*pi*horizon_hours/24)` |
| `anchor_hour_sin` | 요청 기준 시각 hour sin | anchor time 기준 |
| `anchor_hour_cos` | 요청 기준 시각 hour cos | anchor time 기준 |
| `anchor_day_of_year_sin` | 요청 기준 시각 day-of-year sin | anchor time 기준 |
| `anchor_day_of_year_cos` | 요청 기준 시각 day-of-year cos | anchor time 기준 |

`anchor_time`은 요청에 `anchor_time`, `anchor_timestamp_kst`, `base_time`, `forecast_time`, `prediction_time` 중 하나가 있으면 그 값을 사용하고, 없으면 `target_time - horizon_hours`로 계산한다.

---

## 6. 위성/구름 이미지 피처

이미지 입력 shape은 학습/추론에서 다음 두 형태를 처리한다.

```text
(3, 4, 64, 64)
또는
(12, 64, 64)
```

`(3, 4, 64, 64)` 형태는 3개 시점, 4개 채널을 의미하고 모델 입력 전 12채널로 reshape한다.

채널은 다음 4종이다.

| 채널 | 의미 |
|---|---|
| `CA` | cloud amount |
| `CF` | cloud flag/proxy |
| `CT` | cloud type/proxy |
| `CLD` | cloud detection |

정규화 정책:

| 채널 | 정규화 |
|---|---|
| missing value `255` | 0으로 치환 |
| `CA` | binary mode에서 0~1 clip |
| `CF` | binary mode에서 0~1 clip |
| `CT` | `/ 9.0` |
| `CLD` | `/ 3.0` |

현재 live 운영 입력은 실제 NetCDF crop이 아니라 KMA APIHub의 GK2A area 값을 지역 64x64 proxy 이미지로 확장하는 방식이다.

사용 API:

| API | 용도 |
|---|---|
| `getGk2aclaArea` | GK2A cloud amount area |
| `getGk2acldArea` | GK2A cloud detection area |

KMA `SKY` 값도 cloud amount가 비어 있을 때 hint로 사용한다.

proxy 생성 정책:

| proxy 채널 | 생성 방식 |
|---|---|
| `CA` | API 값이 있으면 cloud amount 기반, 없으면 `SKY >= 3`일 때 cloud로 간주 |
| `CLD` | cloud detection을 0~3 범위로 반올림, 없으면 255 |
| `CF_PROXY` | cloud hint가 있으면 1, 아니면 0 |
| `CT_PROXY` | cloud hint가 있으면 3, 아니면 0 |

운영에서는 3개 프레임을 사용한다. 프레임이 부족하면 최신 프레임을 복제하고 warning을 붙인다.

---

## 7. 기상청/KMA 실시간 데이터 수집

운영 추론 서비스의 live 데이터 수집 구현 위치는 다음이다.

```text
C:\Users\SSAFY\PycharmProjects\S14P31S305\ems\ai\service\app\services\live_satellite_service.py
```

사용하는 KMA endpoint는 다음과 같다.

| endpoint | 용도 |
|---|---|
| `nph-dfs_xy_lonlat` | 위경도 -> 기상청 격자 x/y 변환 |
| `nph-dfs_vsrt_grd` | 초단기예보 |
| `nph-dfs_odam_grd` | 관측/실황 fallback |
| `getGk2aclaArea` | GK2A cloud amount area |
| `getGk2acldArea` | GK2A cloud detection area |

인증키는 `KMA_AUTH_KEY` 환경변수로 주입한다. 문서에는 키 값을 기록하지 않는다.

RunPod secret도 같은 이름의 환경변수로 매핑되어 있어야 한다.

```text
KMA_AUTH_KEY = {{ RUNPOD_SECRET_KMA_AUTH_KEY }}
```

RunPod API 호출에 쓰는 `RUNPOD_KEY`는 worker 내부 추론에는 필요하지 않고, 로컬 또는 호출 클라이언트에서 RunPod job을 넣을 때만 필요하다.

---

## 8. GK2A 시간 결측 처리

기상청 GK2A area API는 정시 데이터가 비어 있거나 2분 차이 데이터만 있는 경우가 있었다.

예를 들어 다음처럼 정시 주변 데이터가 실제로 존재하는 케이스를 확인했다.

```text
202605081000 -> 202605080958
202605081100 -> 202605081058
202605081200 -> 202605081200
```

그래서 운영 로직은 정시 exact만 보지 않고 다음 순서로 nearest-time 탐색을 한다.

```text
0, -2, +2, -4, +4, -6, +6, -8, +8, -10, +10 minutes
```

이 방식은 정지궤도 위성 자체의 공전/관측 공백 문제가 아니라, API 제공 시각/처리 완료 시각/상품 생성 지연 문제에 대응하기 위한 운영 보정이다.

---

## 9. 학습 데이터

학습 번들:

```text
satellite_wind_safe_multihorizon_24h_regions_2025_20260508_095509
```

로컬 zip 위치:

```text
C:\Users\SSAFY\Project_Minsu\S305\server_upload\satellite_wind_safe_multihorizon_24h_regions_2025_20260508_095509.zip
```

GPU 서버 작업 위치:

```text
/home/j-k14s305/s305-work
```

GPU 서버 학습 output:

```text
/home/j-k14s305/s305-work/runs/satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted
```

학습 노트북:

```text
C:\Users\SSAFY\PycharmProjects\S14P31S305\ems\ai\test.ipynb
```

데이터 split:

| 파일 | 용도 |
|---|---|
| `samples_daylight_strong_filter_train.parquet` | train |
| `samples_daylight_strong_filter_val.parquet` | clean strong validation |
| `samples_daylight_no_filter_val.parquet` | real no-filter validation |

`real_no_filter_fair_val`은 no-filter validation에서 `(region, target_timestamp_kst)`별로 1~24 전체 horizon이 다 있는 subset이다. horizon별 비교가 더 공정하도록 따로 만든 검증셋이다.

---

## 10. 학습 설정

v10 학습 노트북의 주요 설정은 다음과 같다.

| 항목 | 값 |
|---|---|
| `SEED` | 42 |
| `BATCH_SIZE` | 4096 |
| `EPOCHS` | 55 |
| `PATIENCE` | 10 |
| `MIN_DELTA` | 5e-5 |
| `LR` | 2e-4 |
| `NUM_WORKERS` | 8 |
| `FORCE_RETRAIN` | False |
| optimizer | `AdamW(lr=2e-4, weight_decay=1e-4)` |
| scheduler | `CosineAnnealingLR(T_max=EPOCHS)` |
| base loss | `SmoothL1Loss(beta=0.05, reduction="none")` |

v10의 핵심 변경점은 horizon-balanced loss와 solar/weather/cloud consistency weight를 같이 사용한 것이다.

최종 train weight:

```text
train_weight =
  sample_weight_strong
  * horizon_balance_weight
  * solar_weather_cloud_weight
```

이 값은 과도한 가중치 폭주를 막기 위해 `0.05 ~ 5.0` 범위로 clip한다.

checkpoint metadata에는 다음 정책이 들어간다.

```text
head_policy: short_head_for_1_6h_long_head_for_7_24h
loss: SmoothL1Loss(beta=0.05) weighted by sample_weight_strong * horizon_balance_weight * solar_weather_cloud_weight
image_normalization: binary
```

---

## 11. 학습/런타임 버전

### 11.1 RunPod inference Docker

Dockerfile:

```text
C:\Users\SSAFY\PycharmProjects\S14P31S305\ems\ai\runpod\Dockerfile.inference
```

base image:

```text
pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime
```

RunPod runtime check 결과:

```text
torch: 2.5.1+cu124
cuda available: true
gpu: RTX 4090
```

Docker image에는 `.env` 파일을 포함하지 않는 것으로 확인했다.

### 11.2 RunPod inference requirements

```text
numpy==2.2.5
pandas==2.2.3
scikit-learn==1.6.1
lightgbm==4.6.0
joblib==1.4.2
pyyaml==6.0.2
runpod==1.7.9
astral==3.2
requests==2.32.3
python-dotenv==1.1.0
xarray==2025.1.2
pyproj==3.7.0
netCDF4==1.7.2
h5netcdf==1.4.1
```

### 11.3 Training requirements

학습 서버에서는 PyTorch를 CUDA 환경에 맞게 별도 설치한다. 나머지 주요 requirements는 다음과 같다.

```text
numpy==2.2.5
pandas==2.2.3
scikit-learn==1.6.1
lightgbm==4.6.0
joblib==1.4.2
pyyaml==6.0.2
tqdm==4.67.1
matplotlib==3.10.1
jupyterlab==4.4.1
ipykernel==6.29.5
psycopg2-binary==2.9.10
pg8000==1.31.5
SQLAlchemy==2.0.40
python-dotenv==1.1.0
requests==2.32.3
astral==3.2
xarray==2025.1.2
pyproj==3.7.0
netCDF4==1.7.2
h5netcdf==1.4.1
```

### 11.4 Flask AI service requirements

```text
flask==3.1.0
prometheus-flask-exporter==0.23.1
flask-smorest==0.45.0
marshmallow==3.26.1
redis==5.0.4
psycopg2-binary==2.9.10
typing_extensions>=4.0.0
gunicorn==21.2.0
python-dotenv==1.0.1
```

---

## 12. 검증 결과

v10 최종 검증 summary:

| eval set | rows | MAE | RMSE |
|---|---:|---:|---:|
| clean_strong_val | 48,957 | 0.079356 | 0.100202 |
| real_no_filter_fair_val | 11,880 | 0.109242 | 0.140547 |
| real_no_filter_val | 54,989 | 0.094894 | 0.124597 |

best epoch:

| 항목 | 값 |
|---|---:|
| epoch | 11 |
| train_loss | 0.061294 |
| train_mae | 0.087955 |
| train_rmse | 0.116089 |
| val_mae | 0.079356 |
| val_rmse | 0.100202 |
| lr | 0.000181 |

운영 해석:

```text
real_no_filter_val MAE ~= 0.0949 capacity factor
100 kW 설비 기준 단순 환산 MAE ~= 9.49 kW
```

v8, v9 대비 v10은 real no-filter와 fair validation에서 모두 개선됐다.

| 모델 | clean RMSE | fair RMSE | real RMSE | 해석 |
|---|---:|---:|---:|---|
| v8 | 0.126161 | 0.180198 | 0.152508 | 24h 최초 안정화 |
| v9 | 0.111122 | 0.178220 | 0.141633 | horizon balance 개선 |
| v10 | 0.100202 | 0.140547 | 0.124597 | solar/weather/cloud weighting 개선 |

---

## 13. 지역별/시간별 관찰

v10 real_no_filter_val 기준 지역별 성능:

| region | rows | MAE | RMSE | target_mean | pred_mean |
|---|---:|---:|---:|---:|---:|
| 서울시 | 10,872 | 0.110992 | 0.147183 | 0.363290 | 0.448802 |
| 대전시 | 10,925 | 0.099789 | 0.126225 | 0.411107 | 0.440119 |
| 울산시 | 11,105 | 0.093718 | 0.120523 | 0.450366 | 0.463044 |
| 부산시 | 11,105 | 0.090852 | 0.118268 | 0.453023 | 0.472043 |
| 제주도 | 10,982 | 0.079364 | 0.107725 | 0.341085 | 0.374230 |

서울시는 worst case가 크게 남아 있다. 예를 들어 2025-12-05 11~12시 서울시에서 target capacity factor가 매우 낮은데 모델은 상대적으로 높은 발전 비율을 예측하는 사례가 반복됐다. 이 문제는 단순 구름/태양 조건보다는 KPX 거래량 label의 proxy 한계 또는 정산/집계 특성에서 온 왜곡일 가능성이 있다.

---

## 14. 운영 추론 검증

RunPod에서 v10 Docker 이미지와 checkpoint를 사용해 live 추론을 수행했다.

검증 요청:

```json
{
  "region": "대전시",
  "horizon_hours": 24,
  "target_timestamp_kst": "2026-05-09T12:00:00+09:00",
  "installed_capacity_kw": 100
}
```

검증 응답 핵심:

```text
status: completed
device: cuda
predicted_capacity_factor: 0.8625134825706482
predicted_generation_kw: 86.25134825706482
model_version: satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted
```

이 검증으로 확인한 사항:

- RunPod worker에서 CUDA 사용 가능
- checkpoint 로딩 가능
- KMA secret 주입 가능
- GK2A nearest-time 보정 후 live satellite proxy 생성 가능
- v10 모델로 24h horizon 추론 가능

---

## 15. API 목록

AI 서비스 base URL 예시:

```text
http://localhost:5004
```

문서 endpoint:

```text
Swagger UI: /docs
OpenAPI JSON: /openapi.json
Health: /health
```

현재 AI 서비스의 주요 API는 다음이다.

| Method | Path | 용도 |
|---|---|---|
| GET | `/api/ai/models` | 사용 가능한 AI 모델/메타 정보 조회 |
| POST | `/api/ai/site-profile/structure` | 사이트 구조 기반 프로필 생성/추정 |
| POST | `/api/ai/predict-solar` | 기존 태양광 발전량 예측 API |
| POST | `/api/ai/predict-capacity-factor` | tabular capacity factor 예측 |
| POST | `/api/ai/predict-satellite-capacity-factor` | 위성 feature를 직접 넣는 capacity factor 예측 |
| POST | `/api/ai/predict-live-satellite-capacity-factor` | KMA live 기상/위성 proxy를 수집해 v10 예측 |
| POST | `/api/ai/predict-load` | 부하 예측 |
| POST | `/api/ai/forecast` | 발전/부하 통합 forecast |

중요한 운영 판단:

현재 프론트에서 1~24시간 태양광 예측 그래프를 그릴 때 가장 직접적인 API는 `/api/ai/predict-live-satellite-capacity-factor`다. 이 API를 horizon별로 호출해서 그래프를 채우는 방식이 현재 v10 설계와 가장 맞다.

`/api/ai/forecast`는 기존 통합 forecast 서비스 흐름을 타며, 현재 문맥에서는 v10 live satellite 1~24h 그래프 생성 전용 API로 보는 것은 부정확하다.

---

## 16. 대표 요청/응답 예시

### 16.1 Live satellite capacity factor 요청

```json
{
  "region": "대전시",
  "horizon_hours": 24,
  "target_timestamp_kst": "2026-05-09T12:00:00+09:00",
  "installed_capacity_kw": 100
}
```

### 16.2 응답 의미

```json
{
  "predicted_capacity_factor": 0.8625,
  "predicted_generation_kw": 86.25,
  "model_version": "satellite_wind_safe_multihorizon_24h_v10_solar_weather_cloud_weighted",
  "device": "cuda",
  "warnings": []
}
```

필드 의미:

| 필드 | 의미 |
|---|---|
| `predicted_capacity_factor` | 설비용량 대비 발전 비율 |
| `predicted_generation_kw` | 요청 설비용량 기준 예상 발전 kW |
| `model_version` | 실제 사용된 checkpoint model name |
| `device` | CPU/CUDA 사용 여부 |
| `warnings` | KMA/GK2A fallback, frame 복제 등 운영 경고 |

---

## 17. 왜 v10 방향이 됐는가

초기에는 하루치 예측을 LightGBM 또는 별도 fallback으로 길게 채우는 논의가 있었다. 하지만 프론트 그래프 관점에서는 1~24시간을 서로 다른 모델로 섞어 채우면 특정 구간에서 예측 곡선의 모양이 튀고, 운영 설명도 복잡해진다.

그래서 최종 방향은 다음처럼 정리됐다.

```text
프론트/운영 그래프 기본값:
  v10 단일 모델로 1h~24h 예측

단기 제어/비교:
  v6는 1h, 2h, 3h, 6h short-control champion으로 보관

legacy baseline/challenger:
  LightGBM은 긴 구간 기본 그래프 모델이 아니라 비교군으로 보관
```

v10은 내부적으로 short head와 long head를 분리하므로, 단일 checkpoint 안에서도 단기/장기 horizon의 특성을 다르게 학습한다.

---

## 18. 한계와 리스크

### 18.1 label 한계

학습 target은 실제 현장 인버터 발전량이 아니라 KPX 거래량/실적 기반 proxy다. 따라서 다음 상황에서는 모델이 물리적으로 맞는 예측을 해도 label과 어긋날 수 있다.

- 거래량 집계 지연 또는 정산 보정
- 지역 단위 집계의 혼합 효과
- 설비 구성 변화
- curtailment 또는 계통 제약
- 실제 발전량과 거래량의 시간 정렬 차이

### 18.2 live 위성 proxy 한계

현재 운영 입력은 KMA GK2A area API를 64x64 proxy 이미지로 확장한다. 즉 실제 위성 영상을 crop해서 넣는 고해상도 spatial 입력은 아니다.

다만 구름량/구름탐지/하늘상태를 모델 입력 형태에 맞춰 일관되게 제공하기 때문에, 운영 안정성과 데이터 접근성 면에서는 현재 구조가 더 현실적이다.

### 18.3 API 결측

KMA GK2A API는 정시 exact 데이터가 없고 ±2분 데이터만 있는 경우가 있다. nearest-time fallback으로 완화했지만, API 자체의 일시 결측은 여전히 warning으로 남을 수 있다.

---

## 19. 추후 개선 방향

가장 큰 개선 여지는 실제 사이트 telemetry를 붙이는 것이다.

권장 흐름:

```text
1. v10으로 1~24h 예측 수행
2. 실제 사이트 발전량/인버터 계측값 저장
3. 예측 시점, horizon, region, 설비용량, 기상/위성 snapshot, 실제값을 함께 로그화
4. 일정 기간 누적 후 site calibration 또는 fine-tuning
5. KPX proxy label의 왜곡을 실제 현장 데이터로 보정
```

특히 서울시 worst case처럼 target이 비정상적으로 낮은 구간은 실제 현장 발전량이 있으면 거래량 proxy 문제인지 모델 문제인지 분리할 수 있다.

---

## 20. 관련 파일 위치

로컬 프로젝트:

```text
C:\Users\SSAFY\PycharmProjects\S14P31S305
```

주요 파일:

| 파일 | 설명 |
|---|---|
| `ems\ai\test.ipynb` | v10 학습 노트북 |
| `ems\ai\inference\satellite_wind_safe.py` | satellite/wind-safe 모델 로딩 및 feature 생성 |
| `ems\ai\service\app\services\live_satellite_service.py` | KMA live weather/GK2A 수집 |
| `ems\ai\runpod\Dockerfile.inference` | RunPod inference Dockerfile |
| `ems\ai\runpod\handler.py` | RunPod serverless handler |
| `ems\ai\requirements-runpod-inference.txt` | RunPod inference Python dependencies |
| `ems\ai\requirements-train.txt` | GPU training Python dependencies |
| `ems\ai\checkpoints\satellite_wind_safe_multihorizon_24h_v10\best_model.pt` | v10 checkpoint |

외부 공유/설명 문서 repo:

```text
C:\Users\SSAFY\IdeaProjects\S305
```

관련 문서:

| 파일 | 설명 |
|---|---|
| `AI_DEVELOPMENT_GUIDE.md` | AI 개발 전체 가이드 |
| `10-ai-contracts\README.md` | AI 계약/설계 문서 index |
| `10-ai-contracts\ems-ai-current-design.md` | 현재 AI 설계 |
| `10-ai-contracts\ai-current-runpod-satellite-status.md` | RunPod/v10 운영 상태 |
| `10-ai-contracts\ai-training-inference-strategy.md` | 학습/추론 전략 |
| `10-ai-contracts\prediction-logging-retraining.md` | 예측 로그/재학습 전략 |
| `11-api\README.md` | API 문서 index |
| `11-api\ai-api.md` | AI API 목록 및 사용 설명 |

---

## 21. 컨펌 대상자가 확인해야 할 핵심 질문

1. 프론트 예측 그래프를 v10 단일 모델 1~24h로 채우는 정책에 동의하는가?
2. v6를 운영 기본이 아니라 short-control 비교/보조 모델로 남기는 정책에 동의하는가?
3. KPX 거래량 proxy label의 한계를 인정하고, 이후 실제 사이트 telemetry 기반 보정을 추가하는 방향에 동의하는가?
4. KMA GK2A area API를 proxy 이미지로 쓰는 운영 설계가 현재 단계에서 충분한가?
5. `/api/ai/predict-live-satellite-capacity-factor`를 프론트/제어 서비스의 1~24h 그래프 생성용 API로 쓰는 방향에 동의하는가?

---

## 22. 한 줄 요약

현재 EMS AI는 `satellite_wind_safe_multihorizon_24h_v10`을 기준으로 KMA live 기상, GK2A 구름 proxy, 태양 고도/시간/horizon feature를 결합해 1~24시간 태양광 capacity factor를 예측하고, RunPod CUDA 환경에서 Docker 이미지와 v10 checkpoint로 운영 추론 가능한 상태다.
