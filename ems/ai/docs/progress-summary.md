# AI Progress Summary

## 2026-04-27 KASI Special Day Collection

- source: 한국천문연구원 특일 정보 `SpcdeInfoService`
- script: `ems/ai/scripts/collect_kasi_special_days.py`
- config: `ems/ai/configs/data_sources/kasi_special_days_example.yaml`
- auth env: `KASI_SERVICE_KEY`
- collected years: `2021 ~ 2026`
- collected endpoints:
  - `/getRestDeInfo`
  - `/getHoliDeInfo`
  - `/get24DivisionsInfo`
- raw output:
  - `G:/내 드라이브/s305-ai-data/raw/calendar/kasi_special_days/YYYY/*.xml`
- metadata:
  - `G:/내 드라이브/s305-ai-data/raw/calendar/kasi_special_days/metadata/collection_manifest.jsonl`
- processed output:
  - `G:/내 드라이브/s305-ai-data/processed/calendar/korea_special_days.csv`
- processed rows: `381`
- processed columns:
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

## Nationwide Expansion Note

- detailed plan: `ems/ai/docs/data/nationwide-training-data-plan.md`
- 소비 prior는 전국 단위 원천 데이터가 대부분 확보된 상태다.
- 소비 쪽 다음 병목은 추가 수집보다 `kepco_city_usage`, `kepco_contract_legal_dong`, `kpx_national_demand`, `korea_special_days.csv` 정규화/join이다.
- 전국 발전 예측 학습은 아직 전남 중심 label/weather 구조라서 추가 수집이 필요하다.
- 전국 발전 예측의 핵심 추가 데이터:
  - KPX 지역별 시간별 태양광 발전량 전체 시도
  - 전국 ASOS station 또는 KMA grid 기반 weather feature
  - 지역별 station/grid 매핑 테이블
  - 가능하면 지역별 태양광 설비용량 또는 capacity metadata

## Done

- KMA ASOS 수집 스크립트 작성 및 수집 완료
- `station_165 = 목포` 확인
- Google Drive 데이터 루트 구조 생성
- KPX 태양광 CSV 정규화 완료
- KPX 태양광 API 일별 수집 스크립트 작성 및 1차 수집 완료
- KMA + KPX 병합 CSV 생성 완료
- `KMA + KPX 2025` 기반 태양광 학습용 train/val split 생성 완료
- 태양광 baseline MLP 로컬 CPU smoke test 완료
- 로컬 CPU checkpoint 기반 validation 배치 추론 CSV 생성 완료
- GPU 학습용 config/runbook 및 G Drive training-ready package 생성 완료
- 소비 예측용 공공 데이터 원천 파일 G Drive 정리 완료
- West Power API 수집 스크립트 초안 작성
- 문서 구조 재정리 시작

## Current Training Target

- 문제: 다음 1시간 태양광 발전량 예측
- 입력: 목포 기상 + 전남 태양광 최근 이력
- 출력: `future_solar_P_kw`

## Current Limitation

- 소비 예측용 실제 현장 부하 데이터가 아직 없다.
- 공공 통계 데이터는 소비 baseline/prior 용도로는 유용하지만, 시간 단위 현장 load 정답 데이터는 아니다.
- 태양광 baseline은 raw tabular feature 기반 1차 모델이므로, 일출/일몰처럼 발전량이 작은 구간의 상대오차가 크다.
- KPX 태양광 API는 개발계정 일일 요청 제한 때문에 날짜 단위로 나눠 꾸준히 수집해야 한다.

## Latest Data Collection

- 실행일: `2026-04-27`
- source: KPX regional hourly solar API
- endpoint: `PvAmountByLocHr/getPvAmountByLocHr`
- 수집 범위: `2024-06-01 ~ 2024-09-06`
- 중단 지점: `2024-09-07` 요청에서 rate limit 도달
- 특이사항: `2024-07-26`은 API 응답 row `0`
- raw output: `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/daily_raw/2024`
- daily CSV: `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/daily_csv/2024`
- monthly filtered CSV: `G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/api/hourly_csv/2024`

## Latest Local CPU Smoke Test

- 실행일: `2026-04-27`
- 설정: `configs/solar_kpx_baseline.yaml`
- checkpoint: `checkpoints/solar_kpx_baseline/best.pt`
- validation rows: `1440`
- validation RMSE: `101042.55`
- validation MAE: `64604.63`
- clipped validation RMSE: `101017.68`
- prediction output: `outputs/solar_kpx_baseline_predictions.csv`
- 주의: 이 결과는 GPU 학습 결과가 아니라 로컬 CPU 기능 검증 결과다.

## Training Ready Package

- package: `G:/내 드라이브/s305-ai-data/artifacts/training_ready/solar_kpx_2025_baseline`
- train rows: `7271`
- validation rows: `1440`
- config: `configs/solar_kpx_baseline_gpu.yaml`
- runbook: `docs/gpu-training-runbook.md`
- GPU 서버에서는 `S305_AI_DATA_ROOT`, `S305_AI_OUTPUT_ROOT` 환경 변수를 잡고 실행한다.

## Latest Load Data Organization

- 실행일: `2026-04-27`
- 시군구별 전력사용량:
  - `G:/내 드라이브/s305-ai-data/raw/load/kepco_city_usage/downloads`
  - coverage: `2021 ~ 2025`
- 계약종별-법정동별 전력데이터:
  - `G:/내 드라이브/s305-ai-data/raw/load/kepco_contract_legal_dong/downloads/2025`
  - coverage: `2025-01 ~ 2025-12`
- 시간별 전국 전력수요량:
  - `G:/내 드라이브/s305-ai-data/raw/load/kpx_national_demand/downloads`
- 동네예보 격자 참고자료:
  - `G:/내 드라이브/s305-ai-data/raw/weather/kma_vilage_forecast/grid_reference`
- API 승인:
  - KMA 동네예보 `getUltraSrtNcst`, `getUltraSrtFcst`, `getVilageFcst`
  - KMA 위경도 -> 격자 변환 `nph-dfs_xy_lonlat`
  - 한국천문연구원 특일 정보 `SpcdeInfoService`
- manifest:
  - `G:/내 드라이브/s305-ai-data/raw/load/metadata/load_data_inventory_manifest.json`
- 소비 예측 방향:
  - 1차는 통계 기반 hourly load prior
  - 실제 현장 `load_kw`가 쌓이면 supervised load forecast로 확장

## Next

- 오프라인 백테스트 흐름 정리
- KPX 태양광 API `2024-09-07`부터 이어서 수집
- 소비 데이터 정규화 스크립트 작성
- KMA 동네예보 API 수집 스크립트 작성
- 한국천문연구원 특일 정보 수집 스크립트 작성
- 소비 예측에 필요한 현장 데이터 스키마 정의
- LLM context 입력 포맷 초안 정의
