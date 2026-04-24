# EMS AI Workspace

`ems/ai`는 EMS용 AI 데이터 수집, 데이터셋 생성, 모델 학습, 오프라인 검증을 담당하는 작업 폴더다.

이 폴더의 목표는 다음 네 가지다.

- 공공데이터와 운영 데이터를 모아 AI 학습용 데이터셋으로 정리한다.
- 발전 예측, 이후에는 소비 예측까지 확장 가능한 baseline 모델을 학습한다.
- 모델을 EMS 추론 경로에 연결하기 전에 오프라인 백테스트로 검증한다.
- 추론 로그와 실제값을 다시 모아 재학습 가능한 구조를 유지한다.

가장 먼저 볼 문서:

- [AI Docs Guide](./docs/GUIDE.md)

## Folder Roles

```text
ems/ai/
  checkpoints/   학습된 모델 체크포인트
  configs/       데이터/학습 설정 파일
  data/          로컬 작업용 data 폴더
  docs/          AI 문서
  logs/          학습 로그
  notebooks/     실험용 노트북
  outputs/       샘플 출력물
  scripts/       수집/전처리/병합/데이터셋 생성 스크립트
  train/         학습 코드
```

현재 실제 원천데이터와 처리 결과는 주로 Google Drive 아래에 쌓인다.

- `G:/내 드라이브/s305-ai-data/raw`
- `G:/내 드라이브/s305-ai-data/processed`
- `G:/내 드라이브/s305-ai-data/artifacts`

## Current Focus

현재 기준 1차 모델은 다음 문제를 푼다.

- 입력: 목포(`station_165`) 기상 + 전남 지역 태양광 발전량 이력
- 출력: 다음 1시간 전남 태양광 발전량(`future_solar_P_kw`)

소비 예측은 아직 공공 통계 데이터 수준까지 확보된 상태이고, 실제 현장 부하 데이터가 쌓이면 다음 단계로 확장한다.

## Why `.gitkeep` Exists

이 저장소에는 빈 폴더가 많다. Git은 빈 폴더를 그대로 추적하지 않기 때문에, 폴더 구조를 저장소에 남기기 위해 `.gitkeep` 파일을 넣어둔다.

예:

- `checkpoints/.gitkeep`
- `logs/.gitkeep`
- `data/raw/.gitkeep`

즉 `.gitkeep`은 실행 코드가 아니라 `이 폴더를 저장소에 남겨두기 위한 자리표시자`다.
