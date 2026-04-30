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
- KMA 동네예보 API 수집 결과
- 공휴일/특일 calendar feature

## Planned Calendar Pipeline

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
