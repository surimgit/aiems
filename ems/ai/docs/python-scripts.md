# Python Scripts

## Latest Added Collector

### `scripts/collect_kasi_special_days.py`

- 역할: 공휴일/국경일/24절기 calendar feature 수집
- API endpoint:
  - `https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService`
- 사용하는 기능:
  - `/getRestDeInfo`
  - `/getHoliDeInfo`
  - `/get24DivisionsInfo`
  - 필요 시 `/getAnniversaryInfo`, `/getSundryDayInfo`
- 주요 입력:
  - `configs/data_sources/kasi_special_days_example.yaml`
  - `.env`의 `KASI_SERVICE_KEY`
- 주요 출력:
  - `raw/calendar/kasi_special_days/YYYY/*.xml`
  - `raw/calendar/kasi_special_days/metadata/collection_manifest.jsonl`
  - `processed/calendar/korea_special_days.csv`
- 현재 수집 상태:
  - years: `2021 ~ 2026`
  - rows: `381`
- 예시:

```bash
python ems/ai/scripts/collect_kasi_special_days.py --config ems/ai/configs/data_sources/kasi_special_days_example.yaml
```

현재 `ems/ai`에서 사용하는 Python 스크립트와 역할을 정리한 문서다.

## 환경 및 데이터 수집

### `scripts/init_data_drive.py`

- 역할: Google Drive 작업 루트에 `raw/processed/artifacts` 폴더 구조 생성
- 주요 입력:
  - `configs/data_sources/google_drive_storage_example.yaml`
- 예시:

```bash
python ems/ai/scripts/init_data_drive.py --config ems/ai/configs/data_sources/google_drive_storage_example.yaml --region jeonnam --station-id 165
```

### `scripts/collect_kma_asos.py`

- 역할: KMA ASOS 시간자료를 월 단위로 수집해 raw txt와 csv 저장
- 주요 입력:
  - `configs/data_sources/kma_asos_example.yaml`
  - `.env`의 `KMA_AUTH_KEY`
- 출력 위치:
  - `raw/kma_asos/<region>/station_<id>/hourly_raw/YYYY/YYYY-MM.txt`
  - `raw/kma_asos/<region>/station_<id>/hourly_csv/YYYY/YYYY-MM.csv`
  - `raw/kma_asos/<region>/station_<id>/metadata/monthly_manifest.jsonl`
- 예시:

```bash
python ems/ai/scripts/collect_kma_asos.py --config ems/ai/configs/data_sources/kma_asos_example.yaml
```

### `scripts/check_kma_station.py`

- 역할: KMA 지점 목록 API로 `station_id`의 지점명과 좌표 확인
- 주요 입력:
  - `configs/data_sources/kma_asos_example.yaml`
  - `.env`의 `KMA_AUTH_KEY`
- 예시:

```bash
python ems/ai/scripts/check_kma_station.py --config ems/ai/configs/data_sources/kma_asos_example.yaml --station-id 165
```

### `scripts/collect_kma_vilage_forecast.py`

- 역할: 운영 추론용 현재/미래 날씨 feature 수집
- 사용하는 API:
  - `getUltraSrtNcst`
  - `getUltraSrtFcst`
  - `getVilageFcst`
  - `nph-dfs_xy_lonlat`
- 주요 입력:
  - `configs/data_sources/kma_vilage_forecast_example.yaml`
  - `configs/data_sources/kma_vilage_forecast_korea_sites_example.yaml`
  - `.env`의 `KMA_AUTH_KEY`
  - `raw/weather/kma_vilage_forecast/grid_reference/동네예보지점좌표(위경도)_202601.xlsx`
- 주요 출력:
  - `raw/weather/kma_vilage_forecast/ultra_srt_ncst`
  - `raw/weather/kma_vilage_forecast/ultra_srt_fcst`
  - `raw/weather/kma_vilage_forecast/vilage_fcst`
  - 수집 manifest

### `scripts/collect_gk2a_cloud.py`

- 역할: GK2A cloud area API 단건/구간 수집 테스트
- 주요 입력:
  - `configs/data_sources/gk2a_cloud_area_example.yaml`
  - `.env`의 `KMA_AUTH_KEY`
- 주요 출력:
  - `raw/weather/gk2a_cloud`
- 비고:
  - APIHub 연결성, 상품/영역 파라미터 확인용이다.

### `scripts/collect_gk2a_le2_archive.py`

- 역할: GK2A LE2 NetCDF 상품을 시간축 기준으로 수집
- 주요 입력:
  - `configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml`
  - `configs/data_sources/gk2a_le2_cloud_archive_half_hour_2025.yaml`
  - `.env`의 `KMA_AUTH_KEY`
- 주요 출력:
  - `raw/weather/gk2a_le2/<PRODUCT>/<AREA>/YYYY/MM/DD/*.nc`
  - `raw/weather/gk2a_le2/manifests/*.json`
- 비고:
  - 현재 상품은 `CLA`, `CLD`, 영역은 `KO` 기준이다.
  - `overwrite: false`이므로 중단 후 재실행하면 기존 `.nc`는 skip된다.
  - APIHub는 과도한 병렬 요청 또는 VPN 출구 IP에서 TLS 연결이 끊길 수 있다.

### `scripts/run_gk2a_le2_archive_monthly.py`

- 역할: GK2A LE2 archive 수집을 월 단위 subprocess로 분할 실행
- 주요 입력:
  - `--start-month YYYY-MM`
  - `--end-month YYYY-MM`
  - `--minute-offset 0|30`
- 예시:

```bash
python ems/ai/scripts/run_gk2a_le2_archive_monthly.py --config ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml --start-month 2025-01 --end-month 2025-12 --minute-offset 0 --stop-on-failure
```

### `scripts/collect_kasi_special_days.py`

- 역할: 공휴일/국경일/24절기 calendar feature 수집
- API endpoint:
  - `https://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService`
- 사용할 기능:
  - `/getRestDeInfo`
  - `/getHoliDeInfo`
  - `/get24DivisionsInfo`
  - 필요 시 `/getAnniversaryInfo`, `/getSundryDayInfo`
- 주요 입력:
  - `configs/data_sources/kasi_special_days_example.yaml`
  - `.env`의 `KASI_SERVICE_KEY`
- 주요 출력:
  - `raw/calendar/kasi_special_days/YYYY/*.xml`
  - `processed/calendar/korea_special_days.csv`

### Planned: load statistics normalizer

- 역할: 소비 예측 baseline용 공공 통계 데이터를 long-format으로 정규화
- 주요 입력:
  - `raw/load/kepco_city_usage/downloads/*.xlsx`
  - `raw/load/kepco_contract_legal_dong/downloads/2025/*.xlsx`
  - `raw/load/kpx_national_demand/downloads/*.csv`
- 주요 출력 예정:
  - `processed/load/kepco_city_usage_long.csv`
  - `processed/load/kepco_contract_legal_dong_2025_long.csv`
  - `processed/load/kpx_national_hourly_profile.csv`
  - `processed/load/load_prior_hourly.csv`

### `scripts/normalize_power_sources.py`

- 역할: 전력거래소(KPX)와 서부발전 태양광 CSV를 시간 단위 long-format CSV로 정규화
- 주요 입력:
  - `raw/kepco/<region>/downloads/*.csv`
  - `raw/west_power/<region>/downloads/*.csv`
- 주요 출력:
  - `raw/kepco/<region>/normalized/kepco_jeonnam_hourly.csv`
  - `raw/west_power/<region>/normalized/west_power_hourly.csv`
  - 각 출력 폴더의 `*_manifest.json`
- 비고:
  - 입력 CSV는 `cp949` 인코딩 기준으로 읽음
  - KPX 데이터는 기본값으로 `전라남도`, `태양광`만 필터링
  - 서부발전 데이터는 `01시` ~ `24시` 컬럼을 시간 row로 변환
- 예시:

```bash
python ems/ai/scripts/normalize_power_sources.py
```

### `scripts/collect_kpx_solar_api.py`

- 역할: 한국전력거래소 지역별 시간별 태양광 발전량 API를 날짜 단위로 수집
- 주요 입력:
  - `configs/data_sources/kpx_solar_api_example.yaml`
  - `.env`의 `KPX_SOLAR_SERVICE_KEY`
- 주요 출력:
  - `raw/kepco/<region>/api/daily_raw/YYYY/YYYY-MM-DD.json`
  - `raw/kepco/<region>/api/daily_csv/YYYY/YYYY-MM-DD.csv`
  - `raw/kepco/<region>/api/hourly_csv/YYYY/YYYY-MM.csv`
  - `raw/kepco/<region>/api/metadata/daily_manifest.jsonl`
- 비고:
  - API endpoint: `https://apis.data.go.kr/B552115/PvAmountByLocHr/getPvAmountByLocHr`
  - 날짜별 `tradeYmd=YYYYMMDD` 기준으로 수집
  - `numOfRows=500`이면 하루 전체 데이터가 보통 1회 요청으로 수집됨
  - 개발계정 일일 요청 제한 때문에 `max_requests`로 하루 수집량을 제한
  - 월별 hourly CSV는 설정의 `filter.regions` 기준으로 필터링
- 예시:

```bash
python ems/ai/scripts/collect_kpx_solar_api.py --config ems/ai/configs/data_sources/kpx_solar_api_example.yaml
```

### `scripts/collect_west_power.py`

- 역할: 한국서부발전 신재생에너지 발전량 API를 월 단위로 수집하고 XML, 일별 CSV, 시간 단위 CSV로 저장
- 주요 입력:
  - `configs/data_sources/west_power_api_example.yaml`
  - `.env`의 `WEST_POWER_SERVICE_KEY`
- 주요 출력:
  - `raw/west_power/<region>/monthly_raw/YYYY/YYYY-MM.xml`
  - `raw/west_power/<region>/daily_csv/YYYY/YYYY-MM.csv`
  - `raw/west_power/<region>/hourly_csv/YYYY/YYYY-MM.csv`
  - `raw/west_power/<region>/metadata/monthly_manifest.jsonl`
- 비고:
  - API endpoint: `http://apis.data.go.kr/B552522/pg/reGeneration/getReGeneration`
  - 요청은 월 단위, 응답은 발전기별 일별 `q01 ~ q24`
  - 페이지 처리를 지원하고 XML 응답을 파싱
  - 시간 단위 CSV에는 `generation_kw`, `installed_capacity_kw`, `capacity_factor`를 함께 저장
- 예시:

```bash
python ems/ai/scripts/collect_west_power.py --config ems/ai/configs/data_sources/west_power_api_example.yaml
```

### `scripts/merge_power_weather.py`

- 역할: KMA hourly CSV를 기준 축으로 삼아 KPX 지역 집계와 서부발전 발전기 집계를 `timestamp` 기준으로 병합
- 주요 입력:
  - `raw/kma_asos/<region>/station_<id>/hourly_csv/*/*.csv`
  - `raw/kepco/<region>/normalized/kepco_jeonnam_hourly.csv`
  - `raw/west_power/<region>/normalized/west_power_hourly.csv`
- 주요 출력:
  - `processed/merged/jeonnam_station_165_hourly.csv`
  - `processed/merged/jeonnam_station_165_hourly_manifest.json`
- 비고:
  - KMA를 마스터 시간축으로 사용
  - KPX는 정규화 파일을 그대로 `left join`
  - 서부발전은 발전기명을 키워드로 필터한 뒤 시간별 합계로 집계
  - 기본 서부발전 키워드: `영암,목포,무안,해남,신안,전남`
- 예시:

```bash
python ems/ai/scripts/merge_power_weather.py
```

### `scripts/prepare_solar_kpx_dataset.py`

- 역할: 병합된 `KMA + KPX` 시간 데이터에서 2025년 학습용 태양광 예측 dataset과 train/val split 생성
- 주요 입력:
  - `processed/merged/jeonnam_station_165_hourly.csv`
- 주요 출력:
  - `processed/features/solar_kpx_2025_hourly.csv`
  - `processed/features/solar_kpx_2025_hourly_manifest.json`
  - `processed/splits/solar_kpx_train.csv`
  - `processed/splits/solar_kpx_val.csv`
- 비고:
  - `KPX generation_kw`가 존재하는 2025년 구간만 사용
  - 다음 1시간 발전량(`future_solar_P_kw`)을 기본 target으로 생성
  - 시간 파생 피처, lag, rolling mean, 날씨 피처를 함께 생성
  - 기본 validation 시작 시점은 `2025-11-01 00:00:00`
- 예시:

```bash
python ems/ai/scripts/prepare_solar_kpx_dataset.py
```

### `scripts/audit_download_sources.py`

- 역할: Google Drive raw/processed 자산의 존재 여부와 파일 수를 점검
- 주요 출력:
  - 콘솔 요약
  - 원천 수집 누락 구간 파악용 audit 결과

### `scripts/merge_kpx_capacity_factor_with_asos.py`

- 역할: KPX 5분 태양광 capacity factor 데이터와 ASOS 기상 데이터를 병합
- 주요 입력:
  - `configs/merge/kpx_capacity_factor_with_asos.yaml`
- 주요 출력:
  - capacity factor 학습용 병합 CSV

### `scripts/prepare_kpx_5min_capacity_factor_dataset.py`

- 역할: 5분 단위 KPX capacity factor 데이터를 LightGBM 학습용 train/val split으로 변환
- 주요 입력:
  - `configs/kpx_5min_capacity_factor_with_asos.yaml`
- 주요 출력:
  - `data/processed/kpx_5min_capacity_factor/kpx_5min_capacity_factor_train.csv`
  - `data/processed/kpx_5min_capacity_factor/kpx_5min_capacity_factor_val.csv`

### `scripts/run_operational_solar_forecast.py`

- 역할: 운영형 태양광 예측 요청 payload를 만들고 RunPod inference endpoint에 제출
- 주요 입력:
  - `configs/ops/operational_solar_forecast_example.yaml`
  - `configs/ops/site_profile_example.json`
  - `models/kpx_5min_capacity_factor_lightgbm/model.joblib`
- 주요 출력:
  - RunPod prediction response
  - 저장된 structured profile/context feature가 포함된 forecast payload
  - optional report LLM이 켜진 경우 운영 설명/요약 context

### `scripts/structure_site_profile_with_llm.py`

- 역할: 운영자 자연어 설명을 예측/판단에 사용할 structured site profile JSON으로 변환
- 주요 입력:
  - `configs/ops/llm_site_profile_example.yaml`
  - `.env`의 `OPENAI_API_KEY`
  - `--text` 또는 `--input-file`
- 주요 출력:
  - `outputs/site_profiles/<site_id>_profile.json`
- 검증:

```bash
python ems/ai/scripts/structure_site_profile_with_llm.py --config ems/ai/configs/ops/llm_site_profile_example.yaml --output ems/ai/configs/ops/site_profile_example.json --validate-only
```

- 비고:
  - LLM은 최종 전력 예측값을 직접 만들지 않는다.
  - LLM 출력은 `site_profile.v1` JSON으로 검증한 뒤 저장한다.
  - 운영 예측 주기는 저장된 profile을 읽어 context feature로 사용한다.

### `scripts/build_load_prior.py`

- 역할: 업종별/계약종별 월간 소비량을 시간대별 소비 baseline으로 분배
- 주요 입력:
  - `configs/ops/load_prior_example.yaml`
  - `raw/load/kepco_city_usage/downloads/*.xlsx`
  - `raw/load/kpx_national_demand/downloads/*.csv`
  - `processed/calendar/korea_special_days.csv`
  - `configs/ops/site_profile_example.json`
- 주요 출력:
  - `outputs/load_prior/load_prior_example.csv`
  - `outputs/load_prior/load_prior_example_manifest.json`
- 계산 흐름:
  - 월 kWh를 월 평균 kW로 변환
  - KPX 전국 시간별 수요 profile로 시간대 가중치 적용
  - 공휴일/날씨/LLM structured profile 가중치 적용
  - 안전 margin을 더해 `safe_predicted_load_kw` 산출
  - `predicted_load_kw`, `safety_reserve_kw`, 각 weight/reason을 저장

### `scripts/validate_solar_model.py`

- 역할: 학습된 모델 artifact와 validation split을 사용해 모델 로딩/예측/후처리 동작을 검증

### `scripts/smoke_runpod_capacity_factor_local.py`

- 역할: RunPod handler를 로컬에서 capacity factor 모델 payload로 smoke test

### `scripts/smoke_runpod_predict_local.py`

- 역할: RunPod handler를 로컬에서 기존 solar kw 모델 payload로 smoke test

## 학습

### `train/train.py`

- 역할: baseline MLP 학습 실행
- 입력:
  - `configs/baseline.yaml`
  - `configs/solar_kpx_baseline.yaml`
- 기능:
  - config 로딩
  - csv/parquet dataset 로딩
  - train/val loop
  - metrics 저장
  - checkpoint 저장
- 예시:

```bash
PYTHONPATH=ems/ai python -m train.train --config ems/ai/configs/solar_kpx_baseline.yaml
```

### `train/infer.py`

- 역할: 학습된 checkpoint로 batch inference 실행
- 기본 입력:
  - `configs/solar_kpx_baseline.yaml`
  - `checkpoints/<run_name>/best.pt`
  - config의 validation CSV
- 주요 출력:
  - `outputs/<run_name>_predictions.csv`
- 기능:
  - checkpoint 로드
  - 입력 CSV 로딩
  - `predicted_solar_P_kw` 생성
  - 음수 발전량 보정용 `predicted_solar_P_kw_clipped` 생성
  - target column이 있으면 MAE/RMSE/MAPE 계산
- 예시:

```bash
PYTHONPATH=ems/ai python -m train.infer --config ems/ai/configs/solar_kpx_baseline.yaml --include-target-metrics
```

### `train/dataset.py`

- 역할: csv/parquet 파일을 읽어 `torch Dataset`으로 변환

### `train/model.py`

- 역할: baseline MLP 모델 정의

### `train/metrics.py`

- 역할: `MAE`, `RMSE`, `MAPE` 계산

### `train/checkpoint.py`

- 역할: `latest`, `epoch_xxx`, `best` checkpoint 저장 및 로드

### `train/logger.py`

- 역할: `train.log`, `metrics.jsonl` 저장

### `train/config.py`

- 역할: YAML config 로딩
