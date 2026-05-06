# AI Docs Guide

## Current Final Docs

- [EMS AI Current Design](./AI_CURRENT_FINAL_DESIGN.md)
- [Baseline Solar Training Result](./ml/baseline-training-result.md)
- [Satellite Image Training Handoff - 2026-05-06](./ml/satellite-image-training-handoff-2026-05-06.md)
- [Load Profile And LLM Structuring](./ml/load-profile-and-llm.md)
- [AI Code Map](./ops/ai-code-map.md)
- [GK2A Download Ops Note](./ops/gk2a-download-ops-note.md)

이 문서는 `ems/ai` 문서를 빠르게 찾기 위한 진입점이다.

문서 읽는 순서는 아래를 권장한다.

1. [Data Asset Inventory](./data/data-inventory.md)
2. [Workspace Overview](./overview/workspace-overview.md)
3. [Data Pipeline](./data/data-pipeline.md)
4. [Load Forecast Data Plan](./data/load-forecast-data-plan.md)
5. [Model Strategy](./ml/model-strategy.md)
6. [Inference And Retraining](./ml/inference-and-retraining.md)
7. [Satellite Image Training Handoff - 2026-05-06](./ml/satellite-image-training-handoff-2026-05-06.md)
8. [GPU Training Runbook](./ml/gpu-training-runbook.md)
9. [LLM Role](./ml/llm-role.md)
10. [Repo Structure](./ops/repo-structure.md)
11. [Python Scripts](./python-scripts.md)

## Shared Project Docs

## Global Solar Training Plan

- [global-solar-training-plan.md](./ml/global-solar-training-plan.md): NASA POWER 글로벌 데이터 정의, 학습 진행 방식, 부족 데이터 정리
- [gpu-training-stages.md](./ml/gpu-training-stages.md): GPU 서버에서 1차 MLP, 2차 LightGBM, 3차 site correction을 실행하는 절차

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
- [load-forecast-data-plan.md](./data/load-forecast-data-plan.md): 소비 예측용 공공 데이터, 누락 데이터, baseline 전략 정리

### `ml/`

- [model-strategy.md](./ml/model-strategy.md): 지금 어떤 모델을 학습시키는지와 이유
- [inference-and-retraining.md](./ml/inference-and-retraining.md): 추론, 로그 적재, 재학습 구조
- [satellite-image-training-handoff-2026-05-06.md](./ml/satellite-image-training-handoff-2026-05-06.md): GK2A 위성 이미지 직접 학습, anomaly filter 비교 결과, 다음 작업 메모
- [gpu-training-runbook.md](./ml/gpu-training-runbook.md): GPU 서버 학습 준비, 환경 변수, 실행 명령
- [llm-role.md](./ml/llm-role.md): LLM이 추론 시점에서 어떤 역할을 하는지 설명

### `ops/`

- [repo-structure.md](./ops/repo-structure.md): 폴더 구조, `.gitkeep`, 정리 원칙
- [ai-code-map.md](./ops/ai-code-map.md): 런타임 기준 코드/스크립트 역할 맵
- [gk2a-download-ops-note.md](./ops/gk2a-download-ops-note.md): GK2A 다운로드 경로, 실패 패턴, 재시작/운영 메모
- [gpu-env-setup.md](./gpu-env-setup.md): GPU 환경 셋업

### Root Docs

- [python-scripts.md](./python-scripts.md): 스크립트 카탈로그
- [progress-summary.md](./progress-summary.md): 현재 AI 작업 진행 요약
- [jira/train.md](./jira/train.md): 학습 작업 체크리스트
- [jira/data.md](./jira/data.md): 데이터 작업 체크리스트
- [jira/infer.md](./jira/infer.md): 추론 작업 체크리스트
