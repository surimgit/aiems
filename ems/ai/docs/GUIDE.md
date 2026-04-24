# AI Docs Guide

이 문서는 `ems/ai` 문서를 빠르게 찾기 위한 진입점이다.

문서 읽는 순서는 아래를 권장한다.

1. [Data Asset Inventory](./data/data-inventory.md)
2. [Workspace Overview](./overview/workspace-overview.md)
3. [Data Pipeline](./data/data-pipeline.md)
4. [Model Strategy](./ml/model-strategy.md)
5. [Inference And Retraining](./ml/inference-and-retraining.md)
6. [LLM Role](./ml/llm-role.md)
7. [Repo Structure](./ops/repo-structure.md)
8. [Python Scripts](./python-scripts.md)

## Shared Project Docs

팀 공용 설계 문서는 아래 루트를 기준으로 본다.

- [AI Development Guide](../../../IdeaProjects/S305/AI_DEVELOPMENT_GUIDE.md)
- [AI Training And Inference Strategy](../../../IdeaProjects/S305/10-ai-contracts/ai-training-inference-strategy.md)
- [Solar Forecast Problem](../../../IdeaProjects/S305/10-ai-contracts/solar-forecast-problem.md)
- [Training Dataset Contract](../../../IdeaProjects/S305/10-ai-contracts/training-dataset.md)
- [Forecast Contract](../../../IdeaProjects/S305/10-ai-contracts/forecast-contract.md)

## Local AI Docs Map

### `overview/`

- [workspace-overview.md](./overview/workspace-overview.md): `ems/ai` 폴더가 담당하는 일과 현재 범위

### `data/`

- [data-inventory.md](./data/data-inventory.md): 데이터 자산 대장. 경로, 기간, 파일, 생성 스크립트, 활용 목적까지 정리
- [data-pipeline.md](./data/data-pipeline.md): 원천데이터가 어떻게 학습용 데이터셋으로 가공되는지 설명

### `ml/`

- [model-strategy.md](./ml/model-strategy.md): 지금 어떤 모델을 학습시키는지와 이유
- [inference-and-retraining.md](./ml/inference-and-retraining.md): 추론, 로그 적재, 재학습 구조
- [llm-role.md](./ml/llm-role.md): LLM이 추론 시점에서 어떤 역할을 하는지 설명

### `ops/`

- [repo-structure.md](./ops/repo-structure.md): 폴더 구조, `.gitkeep`, 정리 원칙
- [gpu-env-setup.md](./gpu-env-setup.md): GPU 환경 셋업

### Root Docs

- [python-scripts.md](./python-scripts.md): 스크립트 카탈로그
- [progress-summary.md](./progress-summary.md): 현재 AI 작업 진행 요약
- [jira/train.md](./jira/train.md): 학습 작업 체크리스트
- [jira/data.md](./jira/data.md): 데이터 작업 체크리스트
- [jira/infer.md](./jira/infer.md): 추론 작업 체크리스트
