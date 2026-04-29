# Load Forecast Data Plan

이 문서는 소비 예측을 위해 확보한 공공 데이터와 아직 필요한 데이터를 정리한다.

## Current Position

발전 예측은 시간 단위 발전량 label과 기상 feature가 있어 ML 학습이 가능하다.

소비 예측은 아직 실제 EMS 현장 `load_kw` 시간 단위 label이 없다. 따라서 현재 단계에서는 아래 방식이 현실적이다.

```text
지역/업종/계약종별 월 사용량
  + 전국 시간대별 수요 profile
  + 기상 feature
  + 요일/공휴일/운영자 context
    -> 시간대별 소비 baseline/prior
```

즉 1차 소비 예측은 supervised load forecast가 아니라 통계 기반 load prior다.

## Stored Raw Assets

기준 루트:

```text
G:/내 드라이브/s305-ai-data
```

### KEPCO City Usage

- source: 한국전력공사 시군구별 전력사용량
- local source: `C:/Users/SSAFY/Downloads/시군구별전력사용량`
- G Drive path: `raw/load/kepco_city_usage/downloads`
- coverage:
  - `2021`
  - `2022`
  - `2023`
  - `2024`
  - `2025`
- sheets:
  - `계약종별`
  - `용도업종별`
- unit: `kWh`
- role:
  - 지역별 월 소비 baseline
  - 업종별/계약종별 월 소비 prior

### KEPCO Contract Legal-Dong Usage

- source: 한국전력공사 계약종별-법정동별 전력데이터
- G Drive path: `raw/load/kepco_contract_legal_dong/downloads/2025`
- files:
  - `(제공) 2501_06_계약종별-법정동별 전력데이터.xlsx`
  - `(제공) 2507_12_계약종별-법정동별 전력데이터.xlsx`
- coverage:
  - `2025-01 ~ 2025-12`
- main columns:
  - `년도`
  - `월`
  - `시도`
  - `시군구`
  - `읍면동(법정동)`
  - `계약종별`
  - `고객호수`
  - `판매량`
  - `판매요금`
- role:
  - 더 세밀한 지역 단위 소비 prior
  - 계약종별 고객 수와 판매량 기반 site type prior

### KPX National Hourly Demand

- source: 한국전력거래소 시간별 전국 전력수요량
- G Drive path: `raw/load/kpx_national_demand/downloads`
- file:
  - `한국전력거래소_시간별 전국 전력수요량_20251231.csv`
- encoding:
  - `cp949` 계열로 읽어야 한다.
- structure:
  - `날짜`
  - `1시 ~ 24시`
- role:
  - 월별 소비량을 시간별 load profile로 분배하는 기준 profile
  - 평일/주말/계절별 시간대 가중치 산출

### KMA Village Forecast Grid Reference

- source: 동네예보지점좌표 위경도 참고자료
- G Drive path: `raw/weather/kma_vilage_forecast/grid_reference`
- file:
  - `동네예보지점좌표(위경도)_202601.xlsx`
- main columns:
  - `행정구역코드`
  - `1단계`
  - `2단계`
  - `3단계`
  - `격자 X`
  - `격자 Y`
  - `경도(초/100)`
  - `위도(초/100)`
- role:
  - KMA 동네예보 API 호출에 필요한 `nx`, `ny` 확보

## KMA API Key

- env path: `G:/내 드라이브/s305-ai-data/.env`
- variable: `KMA_AUTH_KEY`
- 주의:
  - 문서에는 키 값을 직접 기록하지 않는다.
  - 스크립트는 `.env`에서 읽도록 한다.

## Needed But Not Yet Collected

### KMA Village Forecast API Authorization / Collection

운영 추론용 미래 날씨 feature를 위해 아래 API 사용 여부를 확인하고 수집 스크립트를 작성해야 한다.

- `getUltraSrtNcst`: 초단기실황조회
- `getUltraSrtFcst`: 초단기예보조회
- `getVilageFcst`: 단기예보조회
- `nph-dfs_xy_lonlat`: 임의 위·경도 -> 인근 동네예보 격자 번호 변환

필요 변수:

- `T1H` / `TMP`: 기온
- `REH`: 습도
- `WSD`: 풍속
- `SKY`: 하늘상태
- `PTY`: 강수형태
- `RN1` / `PCP`: 강수량
- `POP`: 강수확률

현재 상태:

- 동네예보 3개 API 승인 완료
- 위경도 -> 격자 변환 API 승인 완료
- 격자 참고 엑셀도 보유 중이므로 변환 API는 사이트 신규 등록/검증용으로 사용

### KASI Special Day API Authorization / Collection

한국천문연구원 특일 정보 API 승인 완료.

- endpoint: `https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService`
- data format: `XML`
- daily traffic: `10000`
- authorized period: `2026-04-27 ~ 2028-04-27`
- key:
  - 공공데이터포털 일반 인증키 사용
  - 문서에는 키 값을 직접 기록하지 않는다.

사용할 상세 기능:

- `/getRestDeInfo`: 공휴일 정보 조회
- `/getHoliDeInfo`: 국경일 정보 조회
- `/get24DivisionsInfo`: 24절기 정보 조회
- `/getAnniversaryInfo`: 기념일 정보 조회
- `/getSundryDayInfo`: 잡절 정보 조회

EMS AI 1차 활용 우선순위:

1. `/getRestDeInfo`
   - 휴일/대체공휴일 여부
   - 소비 baseline의 weekday/weekend/holiday profile 분기
2. `/getHoliDeInfo`
   - 국경일 feature
3. `/get24DivisionsInfo`
   - 계절 feature 보조

예상 처리 결과:

```text
processed/calendar/korea_special_days.csv
```

예상 컬럼:

- `date`
- `name`
- `category`
- `is_holiday`
- `source`

### Actual Site Load

실제 supervised 소비 예측 모델에는 아래 데이터가 필요하다.

- `timestamp`
- `site_id`
- `load_kw`
- 설비별 load breakdown
- 운영 이벤트/스케줄
- site type
- 휴일/특일

현재는 이 데이터가 없으므로 직접 label 기반 load model은 아직 만들지 않는다.

### KPX Solar API Remaining Dates

발전 데이터 보강용으로 아래 구간이 남아 있다.

- next start: `2024-09-07`
- target end: `2025-12-31`

### West Power API Remaining Months

발전기 단위 상세 발전량 보강용으로 아래 구간이 남아 있다.

- collected: `2024-01 ~ 2024-05`
- remaining: `2024-06 ~ 2025-12`
- note: 현재 설정과 인증키 정리가 필요하다.

## First Load Baseline Strategy

1. `kepco_city_usage`를 long-format으로 정규화한다.
2. `kepco_contract_legal_dong`을 long-format으로 정규화한다.
3. `kpx_national_demand`에서 월/요일/시간대별 profile을 만든다.
4. 지역/업종/계약종별 월 kWh를 시간대 profile로 분배한다.
5. KMA 관측/예보 기상 feature로 냉난방 가중치를 적용한다.
6. 결과를 `predicted_load_kw` baseline으로 EMS에 연결한다.

## Expected Output

초기 산출물은 아래 형태를 목표로 한다.

```text
processed/load/load_prior_hourly.csv
```

예상 컬럼:

- `timestamp`
- `region`
- `city`
- `legal_dong`
- `contract_type`
- `industry_type`
- `monthly_kwh`
- `hourly_profile_weight`
- `predicted_load_kw`
- `source`
