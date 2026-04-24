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

소비 예측으로 확장할 때는 아래 데이터가 추가되어야 한다.

- 실제 EMS `load_kw`
- 운영 이벤트/스케줄
- 설비 상태
- 사이트 유형 정보

그 이후 파이프라인은 아래처럼 확장된다.

```text
Public baseline + Site load history + Operator context
  -> merged site dataset
  -> load feature dataset
  -> load forecast model
```
