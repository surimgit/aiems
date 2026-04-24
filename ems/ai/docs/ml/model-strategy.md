# Model Strategy

## Current Model

현재 바로 학습 가능한 모델은 `태양광 발전량 1시간 ahead 예측 모델`이다.

- 입력:
  - 최근 발전량
  - lag feature
  - rolling mean
  - 기상 feature
  - 시간 파생 feature
- 출력:
  - `future_solar_P_kw`

## Why This Model Comes First

현재 공공데이터만으로 가장 현실적으로 만들 수 있는 모델이기 때문이다.

- 발전 예측:
  - `KMA + KPX`만으로 baseline 가능
- 소비 예측:
  - 공공 통계만으로는 한계가 큼
  - 실제 현장 부하 데이터가 필요

## Baseline Model Type

현재 baseline 학습 코드는 `PyTorch MLP`다.

MLP를 먼저 쓰는 이유:

- 구조가 단순하다.
- 빠르게 학습/검증 가능하다.
- feature engineering 결과를 바로 시험해볼 수 있다.

이후 비교 후보:

- XGBoost / LightGBM
- LSTM / GRU
- Transformer 계열

## What Is Not A Primary Learning Target

### ESS

ESS는 1차적으로 별도 예측 모델로 학습시키지 않는다.

현재 구조:

- AI:
  - 발전 예측
  - 이후 소비 예측
- EMS 정책 엔진:
  - `net_power` 계산
  - SOC 계산
  - 충전/방전 판단

### LLM

LLM은 예측 모델 본체가 아니다.

역할:

- 사용자/운영자의 자연어 입력을 읽는다.
- 이를 구조화된 context feature로 변환한다.
- 추론 시점에 수치 모델을 보조한다.
