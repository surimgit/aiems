# Repo Structure

## Current Rule

`ems/ai` 문서는 아래 흐름으로 읽히도록 정리한다.

```text
README.md
  -> docs/GUIDE.md
      -> docs/overview/*
      -> docs/data/*
      -> docs/ml/*
      -> docs/ops/*
```

## What Each Folder Means

- `checkpoints/`: 학습 모델 저장 위치
- `configs/`: 수집/학습 설정 파일
- `data/`: 로컬 작업용 폴더
- `docs/`: 문서
- `logs/`: 학습 로그
- `notebooks/`: 실험성 노트북
- `outputs/`: 샘플 출력물
- `scripts/`: 수집/전처리/데이터셋 생성 스크립트
- `train/`: 모델 코드

## Cleanup Direction

정리 원칙은 다음과 같다.

1. 루트 README는 개요와 진입점만 가진다.
2. GUIDE는 문서 위치 안내만 담당한다.
3. 상세 설명은 `docs` 하위 기능별 문서에 쌓는다.
4. 스크립트 설명은 문서에서 관리하고, 스크립트 파일명은 역할이 드러나게 유지한다.
5. 임시 실험 결과는 `outputs/` 또는 별도 작업 브랜치에서만 관리한다.

## About `.gitkeep`

Git은 빈 폴더를 저장하지 않는다.

그래서 아래 같은 폴더를 저장소에 남기기 위해 `.gitkeep`을 넣는다.

- `checkpoints/`
- `logs/`
- `outputs/`
- `data/raw/`
- `data/processed/`

즉 `.gitkeep`은 코드나 설정이 아니라 `빈 폴더를 버전관리하기 위한 파일`이다.

## Local `data/` vs Google Drive

현재 실제 원천데이터는 Google Drive 쪽이 기준이다.

- `G:/내 드라이브/s305-ai-data`

`ems/ai/data`는 아래 용도로 본다.

- 로컬 테스트
- 임시 실험
- 예시 경로

실운영용 원천데이터와 처리 결과는 Google Drive 경로를 우선 기준으로 한다.
