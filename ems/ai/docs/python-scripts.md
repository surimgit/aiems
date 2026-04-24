# Python Scripts

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

## 학습

### `train/train.py`

- 역할: baseline MLP 학습 실행
- 입력:
  - `configs/baseline.yaml`
- 기능:
  - config 로딩
  - csv/parquet dataset 로딩
  - train/val loop
  - metrics 저장
  - checkpoint 저장
- 예시:

```bash
python -m train.train --config ems/ai/configs/baseline.yaml
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
