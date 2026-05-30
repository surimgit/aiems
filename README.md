# AIEMS

> MSA 기반 마이크로그리드 EMS 실시간 모니터링 및 AI 예측 시스템

<p align="center">
  <img src="./docs/assets/readme/s305-cover.png" alt="AIEMS main dashboard" width="900" />
</p>

AIEMS는 마이크로그리드 운영 환경을 가정해 시뮬레이터, 데이터 수집, 상태 처리, AI 예측, 제어, 대시보드를 분리된 서비스로 연결한 EMS 프로젝트입니다.

단순 API 호출 중심 구조가 아니라 MQTT와 Redis Streams를 기준으로 서비스 간 책임을 나누고, 실시간 telemetry가 상태 계산, 예측, 저장, 운영 화면까지 이어지는 이벤트 기반 MSA 흐름을 구축하는 데 초점을 두었습니다.

## 핵심 기능

- 시뮬레이터 telemetry를 MQTT로 수집하고 표준 envelope으로 정규화
- Redis Streams 기반 producer/consumer 구조로 수집, 상태 처리, AI 예측, 저장 책임 분리
- Socket.IO 기반 실시간 장비 상태, 장애 이벤트, 지도/토폴로지 UI 반영
- 태양광 발전량과 부하 예측 결과를 대시보드 그래프로 제공
- 소비 패턴 프롬프트를 구조화해 site load profile 입력으로 활용
- AI는 예측과 운영 판단 보조만 담당하고, 실제 제어는 EMS Rule Engine에서 수행

## Demo Assets

| 구분 | 링크 |
| --- | --- |
| EMS 메인 대시보드 | [aiems-main.mp4](./docs/assets/readme/video/aiems-main.mp4) |
| AI 예측 그래프 | [aiems-ai-graph.mp4](./docs/assets/readme/video/aiems-ai-graph.mp4) |
| 소비 패턴 프롬프트 | [aiems-load-prompt.mp4](./docs/assets/readme/video/aiems-load-prompt.mp4) |
| 장비 에러 상태 반영 | [aiems-fault.mp4](./docs/assets/readme/video/aiems-fault.mp4) |

## Architecture

<p align="center">
  <img src="./docs/assets/readme/s305-architecture.png" alt="AIEMS architecture" width="900" />
</p>

```text
Simulator
  -> MQTT
  -> Ingestion
  -> Redis Streams
  -> State Processor / AI Service / DB Writer
  -> PostgreSQL / TimescaleDB
  -> Gateway + Frontend Dashboard
```

초기 화면 상태는 REST API로 조회하고, 이후 변경분은 State Processor가 `site_state_update` 이벤트를 발행해 프론트엔드가 실시간으로 반영합니다. AI Service는 forecast 결과를 저장하고 최신 예측 조회 API를 통해 운영 그래프가 안정적으로 예측값을 표시하도록 구성했습니다.

## Service Layout

| 서비스 | 포트 | 역할 |
| --- | --- | --- |
| Gateway | 80 | Nginx reverse proxy, frontend 정적 파일, API 라우팅 |
| Ingestion | 5001 | MQTT 수집, telemetry 정규화, Redis Streams 발행 |
| State Processor | 5002 | 센서 상태 계산, 장애/이상 상태 처리, Socket.IO 상태 push |
| Control | 5003 | 설비 제어 명령, Rule Engine, 제어 이벤트 발행 |
| AI Service | 5004 | 발전량/부하 예측, load profile, forecast API |
| DB Writer | 5005 | Redis Streams 소비, 시계열/서비스 DB 저장 |
| TimescaleDB | 5432 | telemetry 시계열 저장 |
| PostgreSQL | 5433 | state, ai, control 서비스 DB 논리 분리 |
| Redis | 6379 | cache, Redis Streams event bus |
| MQTT | 1883 / 9001 | 장비 telemetry 수집, MQTT WebSocket |

## Tech Stack

| 영역 | 기술 |
| --- | --- |
| Frontend | Vue 3, TypeScript, Vite, Pinia, Socket.IO |
| Backend | Python, Flask, Gunicorn |
| Event / Realtime | MQTT, Redis Streams, Socket.IO |
| Database | TimescaleDB, PostgreSQL |
| AI / ML | PyTorch, LightGBM, Scikit-learn, RunPod Serverless, OpenAI API |
| Infra | Docker Compose, Nginx, AWS EC2, Jenkins, Prometheus, Grafana, Loki |

## AI 설계 원칙

AI는 제어 주체가 아니라 예측 계층입니다.

- AI Service는 태양광 발전량과 부하를 예측합니다.
- LLM은 사용자 환경 설명을 구조화하는 데만 사용합니다.
- ESS, 디젤 발전기, 계통 제어 판단은 Control 서비스의 EMS Rule Engine이 수행합니다.
- 모델 출력은 야간/저일사/음수/설비 용량 초과 상황에서 safety postprocess를 거쳐 사용합니다.

## AI 모델 적용 방식

AI는 `ems/ai`에서 학습/검증하고, 운영 시점에는 `ems/ai/service`가 MSA의 AI 런타임 경계가 됩니다. 프론트엔드나 스케줄러가 forecast API를 호출하면 AI Service가 site metadata, 저장된 load profile, 기상/위성 입력, 모델 artifact를 조합해 예측 결과를 만들고 DB에 저장합니다.

```text
Offline
  public data / telemetry / satellite data
  -> preprocessing
  -> model training
  -> model artifact

Runtime
  POST /api/ai/forecast or /api/ai/forecast/scheduled
  -> site metadata / stored load profile resolve
  -> solar forecast
       live_satellite: KMA + GK2A input -> RunPod -> satellite-based solar model
       fallback: LightGBM capacity-factor model
  -> load forecast
       saved site profile + time/weather weights + safety reserve
  -> merge solar/load
  -> predicted_net_load_kw + recommendations
  -> ai_forecast_run / ai_forecast_point 저장
```

### Solar Forecast

| 방식 | 적용 방식 |
| --- | --- |
| 위성/기상 기반 태양광 예측 | KMA 초단기 기상과 GK2A 위성 입력을 구성한 뒤 RunPod Serverless에서 시간대별 태양광 발전 비율을 예측합니다. 운영 그래프에 표시되는 기본 예측 경로입니다. |
| 용량계수 기반 fallback 예측 | 위성 기반 추론이 실패하거나 비활성화된 환경에서 사용하는 LightGBM fallback 경로입니다. 예측한 발전 비율을 설비 용량에 곱해 발전량을 계산하고, 야간/음수/상한 초과 값은 후처리로 보정합니다. |
| 표 형식 데이터 기반 baseline | 기상값, 과거 발전량, 시간 주기 feature를 사용하는 초기 baseline입니다. 현재 운영 기본 경로라기보다 비교 기준과 검증용 경로로 유지합니다. |

`/api/ai/forecast`에서 `solar_backend=live_satellite`를 사용하면 AI Service가 시간대별 target을 만들고 RunPod 추론을 호출합니다. RunPod가 실패하거나 비활성화된 환경에서는 capacity-factor LightGBM 경로로 fallback하고, 응답 `warnings`에 fallback 사유를 남깁니다.

현재 구현은 forecast 요청 payload와 저장된 site metadata/load profile을 중심으로 입력을 조립합니다. Redis latest state에서 AI feature를 자동 구성하는 흐름은 설계 문서에 정의되어 있고, 운영 고도화 단계의 후속 연결 범위로 분리되어 있습니다.

### Load Forecast

부하 예측은 현재 supervised ML 모델이 아니라 규칙/프로파일 기반 prior입니다.

- 사용자가 입력한 현장 설명은 `/api/ai/site-profile/structure` 또는 `/api/ai/site-load-profile`에서 `site_profile.v1` JSON으로 구조화합니다.
- OpenAI API가 활성화되어 있으면 LLM이 JSON 변환만 수행하고, 비활성화 환경에서는 규칙 기반 fallback profile을 생성합니다.
- 운영 예측에서는 저장된 profile을 읽어 `base_load_kw * hour_weight * profile_weight * weather_weight`로 부하를 계산합니다.
- 중요 부하 수준에 따라 safety reserve를 더해 `safe_predicted_load_kw`를 만들고, 태양광 예측과 합쳐 `predicted_net_load_kw`를 계산합니다.

### Forecast Persistence

forecast 결과는 AI DB에 실행 단위와 시간대별 point로 저장됩니다.

| API | 역할 |
| --- | --- |
| `POST /api/ai/forecast` | 태양광/부하 통합 forecast 실행 및 저장 |
| `POST /api/ai/forecast/scheduled` | 스케줄러용 forecast 실행. 기본 backend는 `S305_FORECAST_SOLAR_BACKEND=live_satellite` |
| `GET /api/ai/forecast/latest` | 최신 forecast 조회 |
| `POST /api/ai/forecast/actuals` | 실제값 확정 후 예측 point와 매칭 |
| `GET /api/ai/forecast/accuracy` | 예측값과 실제값 기준 정확도/오차 조회 |

Control 서비스는 이 forecast 결과와 recommendation을 참고하지만, AI 결과가 장비를 직접 제어하지 않습니다. 최종 제어 판단은 EMS Rule Engine과 운영자 승인 경계를 거칩니다.

## Local Run

```bash
# 1. 환경 변수 생성
cp .env.example .env

# 2. 필수 환경 변수 검증
./infra/check_env.sh

# 3. 전체 서비스 실행
docker compose up -d --build
```

서비스 상태 확인:

```bash
curl http://localhost:5001/health
curl http://localhost:5002/health
curl http://localhost:5003/health
curl http://localhost:5004/health
curl http://localhost:5005/health
```

주요 접속 지점:

- Gateway / Frontend: `http://localhost`
- AI Swagger UI: `http://localhost:5004/docs`
- MQTT WebSocket: `ws://localhost:9001`

## Repository Map

```text
S14P31S305/
  frontend/              Vue + TypeScript EMS dashboard
  gateway/               Nginx reverse proxy
  ems/
    ingestion/           MQTT ingestion and stream publisher
    state-processor/     state calculation and realtime publisher
    control/             EMS rule engine and control command service
    db-writer/           TimescaleDB/PostgreSQL writer
    ai/                  AI workspace, training, runtime service, RunPod handler
  simulator/             solar/diesel simulator scenarios
  infra/                 DB init, Redis stream init, MQTT, monitoring, backup
  docs/                  local setup, API, architecture and scenario documents
  11-api/                API handoff documents
  exec/                  porting and deployment manual
```

## 주요 문서

- [로컬 개발 환경 가이드](./docs/LOCAL_DEV_SETUP.md)
- [프론트엔드 구조 가이드](./frontend/README.md)
- [프론트엔드 API 명세](./docs/API_SPEC_FRONTEND.md)
- [AI Workspace](./ems/ai/README.md)
- [AI Current Design](./ems/ai/docs/AI_CURRENT_FINAL_DESIGN.md)
- [AI Forecast Persistence And API Flow](./ems/ai/docs/AI_FORECAST_PERSISTENCE_AND_API_FLOW.md)
- [포팅 매뉴얼](./exec/PORTING_MANUAL.md)
