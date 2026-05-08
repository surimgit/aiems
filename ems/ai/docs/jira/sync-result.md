# Jira Sync Result

Last sync scope:

- New epics/stories/tasks from `service.md`
- New epics/stories/tasks from `ops.md`
- Existing completed infer tasks from `infer.md`

## Created Epics

| Key | Summary |
| --- | --- |
| `S14P31S305-359` | `[AI/SERVICE] Flask AI MSA 서비스 구축` |
| `S14P31S305-388` | `[AI/OPS] 예측 결과 저장 및 재학습 운영 구조 구축` |

## Created AI Service Stories

| Key | Story | Story Points | Status |
| --- | --- | ---: | --- |
| `S14P31S305-360` | `[AI/SERVICE] Flask MVC 구조 분리` | 8 | 완료 |
| `S14P31S305-365` | `[AI/SERVICE] 모델 추론 API 구현` | 7 | 완료 |
| `S14P31S305-370` | `[AI/SERVICE] 발전/소비 통합 Forecast API 구현` | 10 | 완료 |
| `S14P31S305-377` | `[AI/SERVICE] site_profile.v1 프롬프트 구조화 API 구현` | 5 | 완료 |
| `S14P31S305-382` | `[AI/SERVICE] Docker Compose MSA 연동 및 API 문서화` | 5 | 완료 |

## Created AI Ops Stories

| Key | Story | Story Points | Status |
| --- | --- | ---: | --- |
| `S14P31S305-389` | `[AI/OPS] forecast_result 저장 연동` | 8 | 해야 할 일 |
| `S14P31S305-393` | `[AI/OPS] forecast_actual_log 실측 매칭` | 8 | 해야 할 일 |
| `S14P31S305-397` | `[AI/OPS] 예측 오차 분석 배치 구현` | 6 | 해야 할 일 |
| `S14P31S305-401` | `[AI/OPS] GK2A 실패/누락 재처리 운영` | 6 | 완료 |
| `S14P31S305-405` | `[AI/OPS] 재학습 모델 교체 및 Promotion 절차` | 6 | 해야 할 일 |

## Task Point Policy

Story Points were written to Story issues as the sum of child task estimates.
Task estimates were also submitted to Jira through the same Story Point field
when Jira accepted it.

Verified Story Point field:

```text
customfield_10031 = Story Points
```

The generated result snapshot is stored locally under:

```text
ems/ai/outputs/jira_service_ops_result.json
ems/ai/outputs/jira_infer_completed_result.json
```

`outputs/` is a generated folder and is not intended for git.

## Existing Infer Items Completed

| Key | Summary | Result |
| --- | --- | --- |
| `S14P31S305-311` | `infer 진입점 생성` | already complete |
| `S14P31S305-312` | `checkpoint 로드 로직 구현` | already complete |
| `S14P31S305-313` | `입력 데이터 로딩 로직 구현` | already complete |
| `S14P31S305-314` | `예측 실행 및 결과 반환 구현` | already complete |
| `S14P31S305-316` | `샘플 추론 테스트 작성` | already complete |
| `S14P31S305-317` | `예측 결과 검증 기준 정의` | already complete |
| `S14P31S305-319` | `배치 추론 실행 예시 작성` | transitioned to complete |
| `S14P31S305-324` | `향후 API화 또는 배치화 방향 정리` | already complete |

