# AI Service Epic

## Epic
`[AI/SERVICE] Flask AI MSA 서비스 구축`

### Epic Description
EMS 메인 서비스가 HTTP로 호출할 수 있는 Flask 기반 AI MSA를 구축한다.
기존 학습/수집 작업과 런타임 API를 분리하고, 모델 artifact를 로드해 발전/소비 예측과 통합 forecast를 제공한다.

## Stories

### Story 1
`[AI/SERVICE] Flask MVC 구조 분리`

- 스토리포인트: `8`
- 상태: 완료
- 설명: AI 런타임을 `ems/ai/service` 아래 Flask MVC 구조로 분리한다.

#### Tasks
- `service/app/controllers 계층 구성`
  - estimate: `2`
  - 상태: 완료
- `service/app/services 계층 구성`
  - estimate: `2`
  - 상태: 완료
- `service/app/repositories 계층 구성`
  - estimate: `2`
  - 상태: 완료
- `service/app/schemas/domain 계층 구성`
  - estimate: `2`
  - 상태: 완료

### Story 2
`[AI/SERVICE] 모델 추론 API 구현`

- 스토리포인트: `7`
- 상태: 완료
- 설명: 저장된 `model.joblib` artifact를 로드해 태양광/용량계수 예측 API를 제공한다.

#### Tasks
- `model.joblib 로딩 repository 구현`
  - estimate: `2`
  - 상태: 완료
- `/api/ai/predict-solar 구현`
  - estimate: `2`
  - 상태: 완료
- `/api/ai/predict-capacity-factor 구현`
  - estimate: `2`
  - 상태: 완료
- `postprocess 및 capacity clamp 연결`
  - estimate: `1`
  - 상태: 완료

### Story 3
`[AI/SERVICE] 발전/소비 통합 Forecast API 구현`

- 스토리포인트: `10`
- 상태: 완료
- 설명: 메인 EMS가 한 번의 요청으로 같은 target_time의 발전/소비 예측을 받을 수 있도록 통합 forecast API를 구현한다.

#### Tasks
- `/api/ai/forecast 엔드포인트 구현`
  - estimate: `2`
  - 상태: 완료
- `start_time/periods/frequency_hours 기반 target_time 생성`
  - estimate: `2`
  - 상태: 완료
- `태양광 feature 자동 생성`
  - estimate: `2`
  - 상태: 완료
- `소비 예측 target_time 연동`
  - estimate: `2`
  - 상태: 완료
- `predicted_net_load_kw 병합 응답 구현`
  - estimate: `1`
  - 상태: 완료
- `forecast smoke test 검증`
  - estimate: `1`
  - 상태: 완료

### Story 4
`[AI/SERVICE] site_profile.v1 프롬프트 구조화 API 구현`

- 스토리포인트: `5`
- 상태: 완료
- 설명: 운영자/현장 설명 프롬프트를 받아 소비 예측 prior에 사용할 `site_profile.v1` 구조로 변환한다.

#### Tasks
- `/api/ai/site-profile/structure 엔드포인트 구현`
  - estimate: `2`
  - 상태: 완료
- `OpenAI Responses API 연동 경로 구현`
  - estimate: `1`
  - 상태: 완료
- `OpenAI 미설정 시 rule fallback 구현`
  - estimate: `1`
  - 상태: 완료
- `site_profile.v1 validation 구현`
  - estimate: `1`
  - 상태: 완료

### Story 5
`[AI/SERVICE] Docker Compose MSA 연동 및 API 문서화`

- 스토리포인트: `5`
- 상태: 완료
- 설명: AI 서비스를 Docker Compose에 등록하고 Swagger/OpenAPI 및 health check를 제공한다.

#### Tasks
- `ai-service Dockerfile 작성`
  - estimate: `1`
  - 상태: 완료
- `docker-compose ai-service 등록`
  - estimate: `1`
  - 상태: 완료
- `/health 구현`
  - estimate: `1`
  - 상태: 완료
- `/docs 및 /openapi.json 검증`
  - estimate: `1`
  - 상태: 완료
- `AI service README 및 docs 경로 정리`
  - estimate: `1`
  - 상태: 완료

