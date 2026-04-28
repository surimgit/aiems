# Nationwide Training Data Plan

이 문서는 현재 전남/전북 중심으로 짜인 AI 데이터 파이프라인을 전국 단위로 확장할 때 필요한 데이터와 우선순위를 정리한다.

## Current Position

현재 보유 데이터 중 소비 prior 쪽은 이미 전국 단위에 가깝다.

- KEPCO 시군구별 전력사용량: `2021 ~ 2025`, 전국 시군구 단위
- KEPCO 계약종별-법정동별 전력데이터: `2025-01 ~ 2025-12`, 전국 법정동 단위
- KPX 시간별 전국 전력수요량: 전국 hourly profile
- KASI 특일 정보: 전국 공통 공휴일/국경일/24절기 calendar feature
- KMA 동네예보 격자 참고자료: 전국 행정구역 격자 매핑 기준

반면 발전 예측 쪽은 아직 전남 중심이다.

- KMA ASOS: 목포 `station_165`
- KPX 태양광 API: 현재 config는 `전라남도` 필터 중심
- merged/feature/split 산출물: `jeonnam_station_165` 기준

## KASI Special Day Collection

수집 완료일: `2026-04-27`

수집 API:

- `/getRestDeInfo`: 공휴일
- `/getHoliDeInfo`: 국경일
- `/get24DivisionsInfo`: 24절기

수집 범위:

- `2021 ~ 2026`

저장 위치:

```text
G:/내 드라이브/s305-ai-data/raw/calendar/kasi_special_days/YYYY/*.xml
G:/내 드라이브/s305-ai-data/raw/calendar/kasi_special_days/metadata/collection_manifest.jsonl
G:/내 드라이브/s305-ai-data/processed/calendar/korea_special_days.csv
```

정규화 CSV:

- rows: `381`
- columns:
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

관련 코드:

- `ems/ai/scripts/collect_kasi_special_days.py`
- `ems/ai/configs/data_sources/kasi_special_days_example.yaml`

인증키:

- `G:/내 드라이브/s305-ai-data/.env`
- variable: `KASI_SERVICE_KEY`
- 문서에는 실제 key 값을 기록하지 않는다.

## What Is Enough For Nationwide Load Prior

전국 단위 소비 prior는 지금 보유한 원천만으로 1차 구현이 가능하다.

필수 입력:

- 월별 지역/업종/계약종별 kWh
- 전국 시간별 수요 profile
- 공휴일/국경일/24절기 calendar feature

아직 필요한 작업:

- `kepco_city_usage` long-format 정규화
- `kepco_contract_legal_dong_2025` long-format 정규화
- `kpx_national_demand` hourly profile 정규화
- `korea_special_days.csv` calendar join
- `load_prior_hourly.csv` 생성

중요 제한:

- 이 결과는 supervised load model이 아니라 통계 기반 `predicted_load_kw` prior다.
- 실제 현장 `load_kw` label이 없으면 소비 모델 학습으로 부르면 안 된다.

## What Is Missing For Nationwide Solar Training

전국 단위 발전 예측을 제대로 학습하려면 아래 데이터가 더 필요하다.

### 1. Regional Solar Labels

현재 전남만 보는 구조를 전국 시도 단위로 확장해야 한다.

필요 데이터:

- KPX 지역별 시간별 태양광 발전량 API 전체 지역
- 최소 `2024-06-01 ~ 2025-12-31`
- 가능하면 `2021 ~ 2025` 이상

필요 변경:

- `collect_kpx_solar_api.py` config에서 `filter.regions`를 전국 시도 목록으로 확장
- raw 저장 경로를 `raw/kpx/solar_by_region/api`처럼 지역 중립 구조로 재정리
- feature dataset에 `region`을 명시적으로 포함

### 2. Nationwide Weather Features

전국 발전량 label을 쓰려면 각 지역에 대응되는 기상 feature도 전국화해야 한다.

선택지:

- ASOS 전국 주요 관측소 수집
- KMA 동네예보 격자 기반 전국 시군구/대표 grid 수집

권장:

- 과거 학습용은 ASOS 전국 관측소
- 운영 추론용은 KMA 동네예보

필요 작업:

- 지역별 대표 ASOS station 매핑
- 지역별 대표 `nx`, `ny` grid 매핑
- `region`, `station_id`, `nx`, `ny` lookup table 생성

### 3. Capacity / Scale Metadata

지역별 발전량은 설비 규모 차이가 크므로, 전국 모델은 절대 kW만 보면 지역 크기를 외우기 쉽다.

있으면 좋은 데이터:

- 지역별 태양광 설비용량
- 발전원별 설비용량
- 지역별 발전사업자/설비 수

활용:

- `capacity_factor` target 또는 feature 생성
- 지역 규모가 다른 데이터를 한 모델에서 안정적으로 학습

### 4. Calendar And Seasonality

KASI 특일 정보는 이미 전국 공통 feature로 사용 가능하다.

추가로 필요한 것은 데이터가 아니라 feature engineering이다.

- `is_holiday`
- `is_solar_term`
- `day_of_week`
- `is_weekend`
- `month`
- `season`
- `day_of_year_sin/cos`

### 5. Train / Validation Split Redesign

전국 데이터는 시간과 지역을 같이 고려해서 split해야 한다.

권장:

- 기본 검증: 시간 기준 holdout
- 추가 검증: 특정 지역 holdout
- 예: `2025-11 ~ 2025-12` 전체 지역 validation
- 예: 일부 시도를 통째로 validation으로 둬서 지역 일반화 확인

## Priority

전국 확장 우선순위는 아래가 현실적이다.

1. KASI calendar는 완료 상태로 두고 load prior에 join
2. 소비 데이터 정규화 후 전국 `load_prior_hourly.csv` 생성
3. KPX 태양광 API를 전국 시도 단위로 이어서 수집
4. 전국 ASOS station 또는 KMA grid 매핑 테이블 작성
5. 전국 weather 수집
6. `region` 포함 solar feature dataset 재생성
7. 전국 solar baseline 학습

## Bottom Line

소비 prior는 원천 데이터가 거의 모였다. 지금 필요한 것은 추가 수집보다 정규화와 join이다.

전국 발전 예측 학습은 아직 부족하다. 핵심 부족분은 전국 지역별 태양광 label과 그 지역에 맞는 전국 weather feature다.
