# Inference And Retraining

## Core Distinction

추론과 재학습은 분리된 단계다.

### Inference

- 이미 학습된 모델을 사용한다.
- 현재 입력값으로 예측값을 만든다.
- 빠르게 돌아야 한다.
- EMS 운영 경로에 주기적으로 연결된다.

예:

- 지금 날씨와 최근 발전량으로 다음 1시간 발전량 예측

### Retraining

- 새로 쌓인 데이터를 포함해 모델을 다시 학습한다.
- 배치성 작업이다.
- 월별/분기별로 수행할 수 있다.
- 이전 모델보다 좋아질 때만 교체한다.

## Recommended Flow

```text
Initial training
  -> periodic inference
  -> prediction/actual log accumulation
  -> offline backtest
  -> periodic retraining candidate
  -> champion/challenger comparison
  -> promote only if improved
```

## Minimum Log To Keep

재학습과 검증을 위해 최소한 아래는 저장해야 한다.

- `timestamp`
- `predicted_generation_kw`
- `actual_generation_kw`
- `predicted_load_kw`
- `actual_load_kw`
- weather snapshot
- site state
- operator context
- model version

## Why Backtesting Matters

현재 시뮬레이터/EMS에는 시간 가속 기능이 없다.

그래서 모델 검증은 `과거 데이터 백테스트`가 기본이다.

예:

1. 특정 시점까지의 입력만 사용
2. 다음 시점 값을 예측
3. 실제값과 비교
4. 전체 기간에 대해 반복

이 방식으로:

- 모델 버전 비교
- 재학습 효과 확인
- 오차 패턴 분석

이 가능하다.

## Quarterly Retraining

분기 재학습은 가능하지만 자동으로 정확도가 좋아지지는 않는다.

교체 조건은 아래처럼 잡는 것이 안전하다.

1. 분기 데이터 추가
2. 새 모델 학습
3. 최근 holdout 구간에서 이전 모델과 비교
4. 더 좋을 때만 운영 모델 교체
