# AI Ops Epic

## Epic
`[AI/OPS] 예측 결과 저장 및 재학습 운영 구조 구축`

### Epic Description
운영 예측 결과를 저장하고 실측값과 매칭해 오차 분석과 재학습 데이터셋으로 연결하는 운영 구조를 구축한다.
GK2A/KMA 데이터 수집 실패 목록 관리, 재학습 모델 교체, champion/challenger 비교 절차를 포함한다.

## Stories

### Story 1
`[AI/OPS] forecast_result 저장 연동`

- 스토리포인트: `8`
- 상태: 미완료
- 설명: AI forecast 응답을 DB 또는 db-writer 경유로 `forecast_result`에 저장한다.

#### Tasks
- `forecast_result 저장 계약 정의`
  - estimate: `2`
  - 상태: 미완료
- `AI service forecast 저장 adapter 구현`
  - estimate: `3`
  - 상태: 미완료
- `db-writer 또는 forecast DB 연동`
  - estimate: `3`
  - 상태: 미완료

### Story 2
`[AI/OPS] forecast_actual_log 실측 매칭`

- 스토리포인트: `8`
- 상태: 미완료
- 설명: 예측 target_time과 실측 telemetry를 매칭해 예측 오차 로그를 생성한다.

#### Tasks
- `target_time/site_id 기준 매칭 규칙 정의`
  - estimate: `2`
  - 상태: 미완료
- `forecast_actual_log 생성 batch 구현`
  - estimate: `4`
  - 상태: 미완료
- `누락 실측값 처리 정책 구현`
  - estimate: `2`
  - 상태: 미완료

### Story 3
`[AI/OPS] 예측 오차 분석 배치 구현`

- 스토리포인트: `6`
- 상태: 미완료
- 설명: forecast_actual_log를 기준으로 MAE/RMSE/fallback_rate를 계산한다.

#### Tasks
- `MAE/RMSE 계산 구현`
  - estimate: `2`
  - 상태: 미완료
- `fallback_rate 계산 구현`
  - estimate: `2`
  - 상태: 미완료
- `시간대/site별 성능 리포트 생성`
  - estimate: `2`
  - 상태: 미완료

### Story 4
`[AI/OPS] GK2A 실패/누락 재처리 운영`

- 스토리포인트: `6`
- 상태: 완료
- 설명: GK2A 1년치 수집 과정에서 누락, 실패, 거절 목록을 별도 인덱스로 관리하고 재시도한다.

#### Tasks
- `GK2A retry index 생성 스크립트 구현`
  - estimate: `2`
  - 상태: 완료
- `MISSING/FAILED/REJECTED_OR_NO_DATA 분류 구현`
  - estimate: `2`
  - 상태: 완료
- `retry index 기반 재시도 스크립트 구현`
  - estimate: `2`
  - 상태: 완료

### Story 5
`[AI/OPS] 재학습 모델 교체 및 Promotion 절차`

- 스토리포인트: `6`
- 상태: 미완료
- 설명: 재학습된 모델 artifact를 검증하고 운영 모델로 교체하는 절차를 정리한다.

#### Tasks
- `model.joblib 교체 절차 문서화`
  - estimate: `2`
  - 상태: 완료
- `champion/challenger 비교 기준 구현`
  - estimate: `2`
  - 상태: 미완료
- `promotion 결과 기록 방식 구현`
  - estimate: `2`
  - 상태: 미완료

