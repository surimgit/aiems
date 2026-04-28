# Global Solar AI Training Plan

## 1. 현재 확보한 글로벌 데이터

2025년 1년치 NASA POWER hourly 데이터를 5개 글로벌 샘플 사이트에 대해 수집했다.

저장 위치:

```text
G:/내 드라이브/s305-ai-data/raw/weather/nasa_power_global
G:/내 드라이브/s305-ai-data/processed/weather/nasa_power_global
```

로컬 TimescaleDB 적재 테이블:

```text
ai_site_mapping
ai_site_weather_hourly
```

수집 사이트:

| site_id | 국가 | 목적 |
| --- | --- | --- |
| KR_SEOUL | Korea | 한국 기준 데모 |
| US_ARIZONA | United States | 고일사량 건조 지역 |
| DE_BERLIN | Germany | 북반구 온대/저일사량 계절성 |
| AE_DUBAI | UAE | 사막/고일사량 지역 |
| AU_SYDNEY | Australia | 남반구 계절성 |

범위:

```text
2025-01-01 00:00 UTC ~ 2025-12-31 23:00 UTC
5 sites x 8760 hours = 43800 rows
```

## 2. 저장된 데이터 정의

processed CSV는 사이트별로 저장된다.

```text
G:/내 드라이브/s305-ai-data/processed/weather/nasa_power_global/{site_id}/2025-01-01_2025-12-31.csv
```

주요 컬럼:

| 컬럼 | 의미 | 사용 |
| --- | --- | --- |
| `timestamp_utc` | UTC 기준 시간 | 시간축 |
| `site_id` | 사이트 ID | site 구분 |
| `country` | 국가 코드 | 지역 feature |
| `timezone` | 사이트 timezone | 현지 시간 feature 생성 |
| `latitude` | 위도 | 위치 feature |
| `longitude` | 경도 | 위치 feature |
| `installed_capacity_kw` | 설치 용량 | 출력 스케일링 |
| `panel_tilt` | 패널 기울기 | 향후 GTI/보정 feature |
| `panel_azimuth` | 패널 방향 | 향후 GTI/보정 feature |
| `ALLSKY_SFC_SW_DWN` | 실제 하늘 조건 일사량 | 태양광 핵심 입력 |
| `CLRSKY_SFC_SW_DWN` | 맑은 하늘 기준 일사량 | 구름 영향 비교 |
| `T2M` | 2m 기온 | 패널 온도/효율 보정 |
| `RH2M` | 상대습도 | 날씨 feature |
| `WS10M` | 10m 풍속 | 냉각/날씨 feature |
| `PRECTOTCORR` | 강수량 | 비/흐림 feature |
| `clear_sky_ratio` | `ALLSKY / CLRSKY` | 날씨 감쇠율 feature |
| `temperature_factor` | 온도 기반 효율 보정 | baseline 계산 |
| `predicted_solar_kw_baseline` | 100kW 기준 태양광 baseline 예측 | 초기 추론/데모 |
| `source_provider` | `nasa_power_api` 등 | 출처 추적 |

현재 `installed_capacity_kw = 100`은 실제 사이트 용량이 아니라 데모 기준 용량이다.
다른 마이크로그리드에 적용할 때는 아래처럼 스케일링한다.

```text
scaled_prediction_kw =
  predicted_solar_kw_baseline * actual_installed_capacity_kw / 100
```

모델 feature로는 출력값 자체보다 capacity factor를 쓰는 것이 더 안정적이다.

```text
solar_capacity_factor =
  predicted_solar_kw_baseline / installed_capacity_kw
```

## 3. 지금 바로 학습 가능한 모델

현재 supervised 학습이 가능한 모델은 한국 KPX/KMA 기반 태양광 발전량 예측 모델이다.

이유:

- KPX에는 실제 발전량 label이 있다.
- KMA에는 같은 시간대 날씨 feature가 있다.
- 이미 train/validation split이 있다.

현재 학습 입력:

```text
G:/내 드라이브/s305-ai-data/processed/splits/solar_kpx_train.csv
G:/내 드라이브/s305-ai-data/processed/splits/solar_kpx_val.csv
```

현재 설정:

```text
ems/ai/configs/solar_kpx_baseline.yaml
```

학습 명령:

```bash
PYTHONPATH=ems/ai python -m train.train --config ems/ai/configs/solar_kpx_baseline.yaml
```

Windows PowerShell:

```powershell
$env:PYTHONPATH="ems/ai"
python -m train.train --config ems/ai/configs/solar_kpx_baseline.yaml
```

GPU 서버에서 단계별 학습을 실행할 때는 [gpu-training-stages.md](./gpu-training-stages.md)를 따른다.

검증/추론:

```bash
PYTHONPATH=ems/ai python -m train.infer --config ems/ai/configs/solar_kpx_baseline.yaml --include-target-metrics
```

## 4. NASA 글로벌 데이터는 어떻게 쓰는가

NASA 글로벌 데이터는 현재 label이 없다.
즉, 이 데이터만으로는 supervised ML을 바로 학습시키지 않는다.

현재 가능한 용도:

- 전세계 좌표 기반 feature pipeline 데모
- 100kW 기준 태양광 baseline 예측
- 지역별 계절성/일사량 비교
- 향후 site actual 데이터가 생겼을 때 correction model 입력
- 운영 추론 시 외부 날씨/일사량 feature cache

현재 NASA 글로벌 데이터의 의미:

```text
전세계 어디든 site 좌표가 있으면
NASA POWER에서 날씨/일사량 feature를 만들고
설비용량 기준 baseline 태양광 예측을 생성할 수 있다.
```

## 5. 추천 학습 로드맵

### Phase 1. 한국 태양광 supervised baseline

```text
KMA weather + KPX actual solar
  -> predicted_solar_kw
```

모델은 현재 PyTorch MLP baseline을 사용한다.
평가는 validation split의 MAE/RMSE/MAPE를 본다.

### Phase 2. 글로벌 feature/baseline 검증

```text
NASA POWER global weather/solar feature
  -> predicted_solar_kw_baseline
```

이 단계에서는 정확도 검증이 아니라 파이프라인 검증이 목적이다.

확인할 것:

- 5개 국가 site 모두 수집 가능
- 파일 캐시 생성
- DB 적재 가능
- 현지 시간 feature 생성 가능
- capacity factor 형태로 지역별 비교 가능

### Phase 3. 운영 site actual log 축적

운영 시 반드시 저장해야 하는 값:

```text
timestamp
site_id
predicted_solar_kw
actual_solar_kw
weather features
installed_capacity_kw
model_version
fallback_flag
```

### Phase 4. site correction model

충분한 site actual 데이터가 생기면 아래 구조로 확장한다.

```text
final_prediction =
  global_or_region_baseline_prediction * site_correction_model
```

우선 후보는 LightGBM이다.
tabular feature에 강하고, feature importance 확인이 가능하며, site별 보정 모델에 적합하다.

### Phase 5. champion/challenger 재학습

신규 모델은 바로 운영 반영하지 않는다.

```text
current champion
  vs
new challenger
```

같은 holdout 기간에서 비교 후 개선될 때만 승격한다.

## 6. 디젤/ESS/Grid는 ML 학습 대상이 아니다

디젤, ESS, grid purchase는 태양광처럼 외부 자연조건을 맞히는 문제가 아니다.
이 값들은 dispatch simulation 결과로 계산한다.

```text
predicted_solar_kw
+ predicted_load_kw
+ ESS state
+ diesel spec/state
+ grid policy
+ rule engine
  -> predicted_diesel_kw
  -> predicted_ess_charge/discharge_kw
  -> predicted_grid_purchase_kw
  -> predicted_grid_sell_kw
```

디젤에 필요한 값:

```text
diesel_rated_kw
diesel_min_output_kw
diesel_max_output_kw
diesel_ramp_rate_kw_per_min
fuel_capacity_l
fuel_level_l
fuel_consumption_curve
start_delay_sec
min_run_time_sec
fault_status
available_status
```

풍력은 태양광과 비슷하게 ML 예측 라인에 추가한다.
초기에는 turbine power curve baseline, 이후 actual wind log가 쌓이면 ML 모델을 붙인다.

## 7. 아직 부족한 데이터

### 태양광

- 각 실제 site의 `actual_solar_kw`
- 실제 `installed_capacity_kw`
- 실제 `panel_tilt`
- 실제 `panel_azimuth`
- 인버터 효율/손실률
- 음영, 오염, snow/soiling 같은 site-specific 손실 정보

현재 NASA 글로벌 데이터만으로 가능한 것은 baseline 예측까지다.
정확도 평가와 재학습에는 site actual 발전량이 필요하다.

### 소비 Load

- 실제 site별 `actual_load_kw`
- 시설 타입
- 운영 시간
- 월별/일별 사용량
- 휴일/특수일 운영 여부
- 냉난방 설비 영향
- 운영자 context/profile_id

현재는 supervised load model을 만들지 않는다.
초기에는 통계 기반 load prior와 profile rule table로 간다.

### 디젤

- 디젤 정격/최소/최대 출력
- 연료탱크 용량
- 연료 잔량
- 출력별 연료소모 곡선
- 기동 지연 시간
- 최소 운전 시간
- fault/maintenance 상태
- 실제 운전 이력

디젤은 ML 예측보다 dispatch simulation 입력으로 정리해야 한다.

### ESS

- ESS 용량 kWh
- 최대 충전/방전 kW
- 현재 SOC
- 충방전 효율
- SOC 상/하한
- 배터리 온도
- degradation 관련 정보

ESS도 직접 ML 예측 대상이 아니라 dispatch simulation 입력이다.

### Grid

- grid 연결 여부
- 구매/판매 가능 여부
- 계약 전력
- 시간대별 요금
- 판매 단가
- 수전 제한
- 계통 정전/제약 이벤트

grid purchase/sell 예측은 발전/소비/ESS/디젤 dispatch 결과로 계산한다.

## 8. 다음 작업

우선순위:

1. GPU 서버에 `processed/weather/nasa_power_global` 업로드
2. 현장 site 등록 스키마 확정
3. `installed_capacity_kw`, `panel_tilt`, `panel_azimuth`를 실제값으로 관리
4. `forecast_result` / `forecast_actual_log` 테이블 확정
5. 실제 solar/load telemetry와 예측값 매칭
6. 태양광 site correction model용 dataset 생성
7. load prior + profile rule table 구현
8. dispatch simulation 출력 정의

현재 상태 요약:

```text
태양광 글로벌 feature pipeline: 준비됨
태양광 한국 supervised baseline: 학습 가능
글로벌 supervised 태양광 모델: actual_solar_kw 부족
소비 supervised 모델: actual_load_kw 부족
디젤/ESS/Grid: ML이 아니라 rule/dispatch simulation 설계 필요
```
