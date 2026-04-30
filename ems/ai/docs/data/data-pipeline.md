# Data Pipeline

## End-To-End Flow

현재 데이터 파이프라인은 아래 순서로 동작한다.

```text
External source
  -> raw 수집
  -> normalized CSV
  -> merged CSV
  -> feature dataset
  -> train/val split
  -> model training
```

## Current Solar Pipeline

현재 브랜치의 태양광 파이프라인은 두 갈래다.

- 기존 hourly kW baseline: KMA ASOS + KPX hourly 발전량
- 최신 운영 후보: KPX 5분 capacity factor + 시간/태양고도 feature + LightGBM

### 1. KMA 수집

- 스크립트: `collect_kma_asos.py`
- 결과:
  - 월별 raw txt
  - 월별 parsed CSV

### 2. KPX/West Power 정규화

- 스크립트: `normalize_power_sources.py`
- 결과:
  - KPX 시간 단위 CSV
  - West Power 시간 단위 CSV

KPX 태양광은 연간 CSV 외에 일별 API 수집 경로도 둔다.

- 스크립트: `collect_kpx_solar_api.py`
- 기준 파라미터:
  - `tradeYmd=YYYYMMDD`
  - `numOfRows=500`
- 결과:
  - 날짜별 raw JSON
  - 날짜별 전체 지역 CSV
  - 월별 전남 필터 hourly CSV
- 현재 이어받을 날짜:
  - `2024-09-07`

### 3. 기상/발전 병합

- 스크립트: `merge_power_weather.py`
- 마스터 축:
  - KMA hourly timestamp
- 결과:
  - `processed/merged/jeonnam_station_165_hourly.csv`

### 4. 학습용 feature 생성

- 스크립트: `prepare_solar_kpx_dataset.py`
- 결과:
  - feature CSV
  - train split
  - validation split

## KPX 5-Min Capacity Factor Pipeline

운영 예측 후보는 발전량 kW를 직접 예측하기보다 capacity factor를 예측하고,
site별 `installed_capacity_kw`를 곱해 kW로 변환한다.

```text
KPX solar generation
  + installed capacity metadata
  + ASOS/time/solar elevation features
    -> capacity factor dataset
    -> train/val split
    -> LightGBM regressor
    -> postprocessed capacity factor
    -> predicted_solar_kw
```

주요 스크립트:

- `merge_kpx_capacity_factor_with_asos.py`
- `prepare_kpx_5min_capacity_factor_dataset.py`
- `validate_solar_model.py`
- `run_operational_solar_forecast.py`

현재 모델:

- artifact: `ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib`
- train rows: `16,969`
- validation rows: `2,786`
- validation MAE: `0.0181024812`
- validation RMSE: `0.0401897991`
- postprocessed MAE: `0.0177028470`
- postprocessed RMSE: `0.0405369167`

운영 예측 config:

- `ems/ai/configs/ops/operational_solar_forecast_example.yaml`
- RunPod endpoint id 예시: `bmmyj6f7xh82wa`
- model version: `kpx_5min_capacity_factor_lightgbm`

## GK2A Cloud Archive Pipeline

위성 구름 산출물은 KMA APIHub GK2A LE2 archive로 별도 수집한다.

```text
KMA APIHub GK2A LE2
  -> raw/weather/gk2a_le2/<PRODUCT>/KO/YYYY/MM/DD/*.nc
  -> monthly manifest
  -> future cloud feature extraction
```

수집 설정:

- hourly: `configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml`
- half-hour: `configs/data_sources/gk2a_le2_cloud_archive_half_hour_2025.yaml`
- products: `CLA`, `CLD`
- area: `KO`

현재 상태:

- target: `2025-01-01 00:00+09:00 ~ 2025-12-31 23:00+09:00`
- expected files: `17,520`
- collected files: `7,623`
- progress: `43.51%`
- stopped at: `2026-04-30 14:52:54 KST`
- reason: APIHub HTTPS/TLS connection failure after high-volume parallel collection

재개 절차:

1. 원본 네트워크 또는 새 출구 IP에서 단건 Python HTTPS 요청을 먼저 확인한다.
2. 성공하면 `run_gk2a_le2_archive_monthly.py`를 1~2병렬로 재개한다.
3. 안정화되면 4병렬로 늘린다.
4. `overwrite: false`라 기존 `.nc` 파일은 skip된다.

## Why The Pipeline Is Split

단계를 나눈 이유는 다음과 같다.

- 원본 응답을 다시 확인할 수 있다.
- 정규화 규칙을 바꿔도 수집을 다시 안 해도 된다.
- 병합 로직과 학습셋 생성 로직을 분리할 수 있다.
- 문제 생긴 구간만 재처리하기 쉽다.

## Load Forecast Extension

현재 소비 예측은 실제 EMS `load_kw` label이 없으므로 통계 기반 baseline부터 만든다.

확보한 데이터:

- `raw/load/kepco_city_usage/downloads`
  - 시군구별 전력사용량 `2021 ~ 2025`
- `raw/load/kepco_contract_legal_dong/downloads/2025`
  - 계약종별-법정동별 전력데이터 `2025-01 ~ 2025-12`
- `raw/load/kpx_national_demand/downloads`
  - 시간별 전국 전력수요량
- `raw/weather/kma_vilage_forecast/grid_reference`
  - 동네예보 격자 좌표 참고자료
- 한국천문연구원 특일 정보 API
  - 공휴일/국경일/24절기 calendar feature

1차 소비 baseline 파이프라인은 아래와 같다.

```text
KEPCO city/month usage
  + KEPCO contract/legal-dong usage
  + KPX national hourly demand profile
  + KMA observed/forecast weather
  + KASI special-day calendar
  + operator context
    -> hourly load prior
    -> predicted_load_kw
```

현재 구현:

- script: `ems/ai/scripts/build_load_prior.py`
- config: `ems/ai/configs/ops/load_prior_example.yaml`
- source example:
  - KEPCO city usage `용도업종별`
  - region/city: `서울특별시 종로구`
  - industry: `순수써비스`
  - target: `2025-12-01 00:00+09:00 ~ 2025-12-02 23:00+09:00`
- output:
  - `ems/ai/outputs/load_prior/load_prior_example.csv`
  - `ems/ai/outputs/load_prior/load_prior_example_manifest.json`
- generated rows: `48`
- sample predicted load range:
  - min: `107.867334690492 kW`
  - average: `166.605413523525 kW`
  - max: `205.521578634804 kW`
- safety margin:
  - default reserve ratio: `15%`
  - min reserve: `10 kW`
  - output: `safe_predicted_load_kw`

`scale_factor`는 시군구/업종 월간 총사용량 중 해당 site가 차지한다고 보는 비율이다.
실제 현장 telemetry가 들어오기 전까지는 이 값으로 site 규모를 보정한다.

추후 실제 현장 데이터가 쌓이면 아래로 확장한다.

```text
Public load prior
  + Site load history
  + Operator context
    -> load feature dataset
    -> supervised load forecast model
```

아직 필요한 데이터:

- 실제 EMS `load_kw`
- 운영 이벤트/스케줄
- 설비 상태
- 사이트 유형 정보
- KMA 동네예보 API 운영 수집 결과
- 공휴일/특일 calendar feature는 수집 완료됐지만 load prior에 join하는 정규화 작업이 남아 있다.

## Calendar Pipeline

한국천문연구원 특일 정보는 아래 순서로 처리한다.

```text
SpcdeInfoService
  -> raw/calendar/kasi_special_days/YYYY/*.xml
  -> processed/calendar/korea_special_days.csv
  -> load prior calendar features
```

우선 수집 대상:

- `/getRestDeInfo`
- `/getHoliDeInfo`
- `/get24DivisionsInfo`

현재 상태:

- collected years: `2021 ~ 2026`
- processed rows: `381`
- processed output: `G:/내 드라이브/s305-ai-data/processed/calendar/korea_special_days.csv`

## Global NASA POWER Solar Pipeline

전세계 site 데모와 향후 site correction을 위해 NASA POWER 글로벌 태양광/기상 데이터를 별도 파이프라인으로 둔다.

```text
site metadata
  -> NASA POWER hourly data
  -> processed global weather CSV
  -> local TimescaleDB cache
  -> baseline solar prediction / future site correction dataset
```

현재 수집 완료:

- site: `KR_SEOUL`, `US_ARIZONA`, `DE_BERLIN`, `AE_DUBAI`, `AU_SYDNEY`
- range: `2025-01-01 00:00 UTC ~ 2025-12-31 23:00 UTC`
- rows: `43800`
- processed path: `G:/내 드라이브/s305-ai-data/processed/weather/nasa_power_global`
- raw path: `G:/내 드라이브/s305-ai-data/raw/weather/nasa_power_global`
- DB tables: `ai_site_mapping`, `ai_site_weather_hourly`

상세 정의와 학습 계획은 [global-solar-training-plan.md](../ml/global-solar-training-plan.md)를 따른다.
