# Workspace Overview

## What `ems/ai` Owns

`ems/ai`는 EMS AI 작업 중 아래 범위를 담당한다.

- 외부 데이터 수집
- 데이터 정규화와 병합
- 학습용 데이터셋 생성
- baseline 모델 학습
- 오프라인 백테스트
- 추론/재학습 문서화

## Current Scope

현재 1차 범위는 태양광 발전량 예측이다.

- 기상 데이터: KMA ASOS `station_165 = 목포`
- 발전 데이터: KPX 전남 지역 시간별 태양광 발전량
- 학습 목표: 다음 1시간 태양광 발전량 예측

소비 예측은 아직 공공 통계 데이터만 있고, 현장 실제 부하 데이터가 쌓이면 다음 단계로 확장한다.

## Working Principle

현재 AI 구조는 다음 원칙을 따른다.

1. 초기에는 공공데이터 기반 baseline으로 시작한다.
2. EMS 운영 중 쌓이는 실제 데이터로 점점 현장 맞춤 모델로 이동한다.
3. ESS는 1차적으로 별도 학습 대상이 아니라 EMS 정책 엔진이 계산/제어한다.
4. LLM은 추론 시점에서 자연어 운영 맥락을 구조화하는 보조 계층으로 사용한다.

## Immediate Deliverables

현재 바로 만들고 유지해야 하는 산출물은 다음과 같다.

- 원천데이터 저장 구조
- 정규화 CSV
- 병합 CSV
- train/val split CSV
- 학습 config
- 체크포인트와 로그
