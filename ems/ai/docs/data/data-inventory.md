# Data Asset Inventory

이 문서는 현재 AI 작업에서 실제로 사용하는 데이터 자산 대장이다.

기준 원칙:

- 원천데이터와 처리 결과의 기준 위치는 Google Drive다.
- 각 자산은 `어디에 있는지`, `무엇인지`, `어떤 스크립트가 만들었는지`, `어떻게 활용하는지`를 함께 기록한다.

## 1. Base Root

기준 루트:

- `G:/내 드라이브/s305-ai-data`

주요 하위 폴더:

```text
G:/내 드라이브/s305-ai-data
  raw/
  processed/
  artifacts/
```

## 2. Raw Assets

### 2.1 KMA ASOS

#### Asset Group

- 목적: 목포 관측소 기준 시간별 기상 이력 확보
- source: KMA ASOS
- region: `jeonnam`
- station: `165 (목포)`

#### Paths

- 루트:
  - `G:/내 드라이브/s305-ai-data/raw/kma_asos/jeonnam/station_165`
- 설정:
  - `metadata/collection_config.json`
- 수집 로그:
  - `metadata/monthly_manifest.jsonl`
- raw 응답:
  - `hourly_raw/YYYY/YYYY-MM.txt`
- parsed CSV:
  - `hourly_csv/YYYY/YYYY-MM.csv`

#### Current Coverage

- 기간:
  - `2024-01 ~ 2025-12`
- 실제 월 파일 수:
  - `24개월`

#### Main Columns

- `TM`
- `STN`
- `TA`
- `HM`
- `CA_TOT`
- `SI`
- `RN`
- `WS`
- 그 외 KMA ASOS 기본 컬럼

#### Created By

- 수집: [collect_kma_asos.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/collect_kma_asos.py)
- 지점 확인: [check_kma_station.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/check_kma_station.py)

#### How It Is Used

- 발전 예측 모델의 기상 입력
- 병합 데이터셋의 마스터 시간축
- 추후 소비 예측에서도 외생 변수로 사용

---

### 2.2 KPX Solar CSV

#### Asset Group

- 목적: 전남 지역 시간별 태양광 발전량 확보
- source: 한국전력거래소(KPX)

#### Paths

- 원본 다운로드:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/downloads/한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231.csv`
- 정규화 CSV:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/normalized/kepco_jeonnam_hourly.csv`
- 정규화 manifest:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/normalized/kepco_jeonnam_hourly_manifest.json`
- API raw JSON:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/daily_raw/YYYY/YYYY-MM-DD.json`
- API daily CSV:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/daily_csv/YYYY/YYYY-MM-DD.csv`
- API monthly filtered CSV:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/hourly_csv/YYYY/YYYY-MM.csv`
- API manifest:
  - `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/metadata/daily_manifest.jsonl`

#### Current Coverage

- 기간:
  - `2025년`
- 지역 필터:
  - `전라남도`
- 연료 필터:
  - `태양광`
- API 수집 완료:
  - `2024-06-01 ~ 2024-09-06`
- API 다음 수집 시작:
  - `2024-09-07`
- API 특이사항:
  - `2024-07-26`은 row `0`

#### Main Columns After Normalize

- `timestamp`
- `trade_date`
- `hour_ending`
- `region`
- `fuel_type`
- `generation_mwh`
- `generation_kw`
- `source`

#### Created By

- 정규화: [normalize_power_sources.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/normalize_power_sources.py)
- API 수집: [collect_kpx_solar_api.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/collect_kpx_solar_api.py)

#### How It Is Used

- 1차 태양광 발전량 예측의 정답 데이터
- KMA와 병합해 학습용 feature dataset 생성

---

### 2.3 West Power CSV / API Data

#### Asset Group

- 목적: 발전기 단위 상세 태양광 발전량 확보
- source: 한국서부발전

#### Paths

- 원본 CSV:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/downloads/한국서부발전(주)_태양광 발전 현황_20230630.csv`
- 정규화 CSV:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/normalized/west_power_hourly.csv`
- 정규화 manifest:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/normalized/west_power_hourly_manifest.json`

#### API Collection Paths

- 설정:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/metadata/collection_config.json`
- 수집 로그:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/metadata/monthly_manifest.jsonl`
- raw XML:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/monthly_raw/YYYY/YYYY-MM.xml`
- daily CSV:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/daily_csv/YYYY/YYYY-MM.csv`
- hourly CSV:
  - `G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/hourly_csv/YYYY/YYYY-MM.csv`

#### Current Coverage

- CSV snapshot:
  - 과거 기준 데이터
- API 수집 완료:
  - 현재 `2024-01 ~ 2024-05`
- 이후 월:
  - API rate limit 때문에 추가 수집 필요

#### Main Columns After Normalize

- `timestamp`
- `date`
- `hour_ending`
- `generator_name`
- `installed_capacity_mw`
- `installed_capacity_kw`
- `generation_wh`
- `generation_kwh`
- `generation_kw`
- `capacity_factor`

#### Created By

- CSV 정규화: [normalize_power_sources.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/normalize_power_sources.py)
- API 수집: [collect_west_power.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/collect_west_power.py)

#### How It Is Used

- 발전기 단위 상세 발전량 참고 데이터
- 향후 세밀한 발전기 수준 예측이나 capacity factor 분석에 활용 가능
- 현재 1차 태양광 baseline에서는 필수 아님

---

### 2.4 Load Statistics Files

#### Asset Group

- 목적: 소비 예측 baseline/prior 확보
- source: 한국전력공사, 한국전력거래소 통계성 데이터

#### Paths

- 시군구별 전력사용량:
  - `G:/내 드라이브/s305-ai-data/raw/load/kepco_city_usage/downloads`
- 계약종별-법정동별 전력데이터:
  - `G:/내 드라이브/s305-ai-data/raw/load/kepco_contract_legal_dong/downloads/2025`
- 시간별 전국 전력수요량:
  - `G:/내 드라이브/s305-ai-data/raw/load/kpx_national_demand/downloads/한국전력거래소_시간별 전국 전력수요량_20251231.csv`
- load data manifest:
  - `G:/내 드라이브/s305-ai-data/raw/load/metadata/load_data_inventory_manifest.json`

#### Current Coverage

- 시군구별 전력사용량:
  - `2021 ~ 2025`
- 계약종별-법정동별 전력데이터:
  - `2025-01 ~ 2025-12`
- 시간별 전국 전력수요량:
  - 파일명 기준 `2025-12-31` snapshot

#### Main Fields

- 시군구별 전력사용량:
  - `연도`
  - `시도`
  - `시군구`
  - `계약종별`
  - `업종별`
  - `1월 ~ 12월`
- 계약종별-법정동별 전력데이터:
  - `년도`
  - `월`
  - `시도`
  - `시군구`
  - `읍면동(법정동)`
  - `계약종별`
  - `고객호수`
  - `판매량`
  - `판매요금`
- 시간별 전국 전력수요량:
  - `날짜`
  - `1시 ~ 24시`

#### How It Is Used

- 지역별 소비 baseline
- 업종별 소비 prior
- 계약종별/법정동 단위 세부 소비 prior
- 전국 시간대별 수요 profile 기반 hourly load 분배
- 병원/공장/캠퍼스 등 도메인 특성 반영용 통계 입력

주의:

- 이 데이터는 시간 단위 현장 load 정답 데이터가 아니다.
- 소비 예측 모델의 직접 label로 쓰기엔 부족하다.
- 1차 구현은 supervised model이 아니라 통계 기반 `predicted_load_kw` prior로 둔다.

---

### 2.5 KMA Village Forecast Reference

#### Asset Group

- 목적: 운영 추론 시점의 기상 예보 feature 확보 준비
- source: 기상청 동네예보

#### Paths

- 격자 좌표 참고자료:
  - `G:/내 드라이브/s305-ai-data/raw/weather/kma_vilage_forecast/grid_reference/동네예보지점좌표(위경도)_202601.xlsx`
- API key:
  - `G:/내 드라이브/s305-ai-data/.env`
  - variable: `KMA_AUTH_KEY`

#### Current Coverage

- grid reference:
  - `2026-01` 기준
- API collection:
  - 아직 수집 스크립트 미작성

#### Needed APIs

- `getUltraSrtNcst`: 초단기실황조회
- `getUltraSrtFcst`: 초단기예보조회
- `getVilageFcst`: 단기예보조회
- `nph-dfs_xy_lonlat`: 임의 위·경도 -> 인근 동네예보 격자 번호 변환

#### How It Is Used

- 발전 예측 운영 추론 시 미래 날씨 feature
- 소비 baseline의 냉난방 보정 feature
- `nx`, `ny` 격자값 산출 기준

---

### 2.6 KASI Special Day API

#### Asset Group

- 목적: 소비 baseline의 휴일/특일/calendar feature 확보
- source: 한국천문연구원 특일 정보

#### API

- endpoint:
  - `https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService`
- data format:
  - `XML`
- daily traffic:
  - `10000`
- authorized period:
  - `2026-04-27 ~ 2028-04-27`

#### Authorized Functions

- `/getAnniversaryInfo`: 기념일 정보 조회
- `/getRestDeInfo`: 공휴일 정보 조회
- `/getHoliDeInfo`: 국경일 정보 조회
- `/get24DivisionsInfo`: 24절기 정보 조회
- `/getSundryDayInfo`: 잡절 정보 조회

#### Key Management

- 공공데이터포털 일반 인증키 사용
- 문서에는 키 값을 직접 기록하지 않는다.
- `.env` 변수로 관리할 예정

#### Current Coverage

- API 승인 완료
- 수집 스크립트 미작성
- raw/processed 산출물 아직 없음

#### How It Is Used

- 공휴일/대체공휴일 여부
- 국경일/기념일 feature
- 24절기 기반 계절 feature
- 소비 baseline의 시간대 profile 보정

## 3. Processed Assets

### 3.1 Merged Hourly Dataset

#### Path

- `G:/내 드라이브/s305-ai-data/processed/merged/jeonnam_station_165_hourly.csv`
- `G:/내 드라이브/s305-ai-data/processed/merged/jeonnam_station_165_hourly_manifest.json`

#### Created By

- [merge_power_weather.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/merge_power_weather.py)

#### Purpose

- KMA를 기준 시간축으로 KMA + KPX + West Power를 병합
- 학습용 feature dataset 생성 전 중간 산출물

#### Main Usage

- 1차 태양광 학습 데이터셋 생성의 입력

---

### 3.2 Solar Feature Dataset

#### Path

- `G:/내 드라이브/s305-ai-data/processed/features/solar_kpx_2025_hourly.csv`
- `G:/내 드라이브/s305-ai-data/processed/features/solar_kpx_2025_hourly_manifest.json`

#### Created By

- [prepare_solar_kpx_dataset.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/prepare_solar_kpx_dataset.py)

#### Purpose

- `KMA + KPX 2025`에서 1차 학습용 feature/label 생성

#### Main Columns

- `timestamp`
- `past_solar_P_kw`
- `past_solar_P_kw_lag_1`
- `past_solar_P_kw_lag_24`
- `rolling_mean_3h`
- `rolling_mean_24h`
- `temperature`
- `humidity`
- `cloud_cover`
- `irradiance`
- `rainfall_mm`
- `wind_speed`
- `hour_of_day_sin`
- `hour_of_day_cos`
- `day_of_year_sin`
- `day_of_year_cos`
- `future_solar_P_kw`
- `future_solar_P_kw_6h`
- `future_solar_P_kw_24h`

#### How It Is Used

- 현재 PyTorch MLP baseline의 직접 학습 데이터

---

### 3.3 Train / Validation Splits

#### Paths

- `G:/내 드라이브/s305-ai-data/processed/splits/solar_kpx_train.csv`
- `G:/내 드라이브/s305-ai-data/processed/splits/solar_kpx_val.csv`

#### Created By

- [prepare_solar_kpx_dataset.py](C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/scripts/prepare_solar_kpx_dataset.py)

#### Current Split Rule

- validation 시작:
  - `2025-11-01 00:00:00`

#### How It Is Used

- baseline train loop 입력
- 오프라인 성능 검증

## 4. Model Mapping

현재 자산과 모델의 연결은 아래와 같다.

```text
KMA hourly_csv
  + KPX normalized hourly
    -> merged hourly dataset
      -> solar feature dataset
        -> train/val split
          -> solar baseline model
```

## 5. What Is Missing

소비 예측으로 넘어가려면 아래 자산이 추가로 필요하다.

- 실제 현장 `load_kw`
- 운영 이벤트/스케줄
- 사이트 상태
- 추론 로그와 실제값 비교 로그
- KMA 동네예보 API 수집 결과
- 공휴일/특일 calendar feature

즉 현재 자산은 `발전 예측` 학습에는 충분하고, `소비 예측`은 통계 기반 baseline까지 가능하다. 실제 현장 load model은 아직 부족하다.
