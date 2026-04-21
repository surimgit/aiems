# SSAFY S305 - MG(마이크로그리드) 모니터링 시스템

## 프로젝트 개요
Vue.js + TypeScript 프론트엔드, Flask(Python) 백엔드 다중 서비스, MQTT 브로커, TimescaleDB + PostgreSQL(논리 분리), Redis Streams, AI/ML 파이프라인으로 구성된 마이크로그리드 모니터링 시스템.

## 아키텍처
| 레이어 | 구성요소 | 비고 |
|--------|----------|------|
| Web Server | Nginx (Reverse Proxy, HTTPS, WebSocket) | Gateway EC2 |
| Frontend | Vue.js + TypeScript | 정적 파일 배포 |
| Backend | Flask (Python) - 서비스별 분리 | EMS EC2 |
| IoT | MQTT Broker + WebSocket | 실시간 데이터 수집 |
| Time-series DB | TimescaleDB (PostgreSQL 15) | DB EC2 (컨테이너 1) |
| Service DB | PostgreSQL 15 (state/ai/control 3개 논리 분리) | DB EC2 (컨테이너 2) |
| Cache/Event Bus | Redis (캐시) + Redis Streams (이벤트 버스) | EMS EC2 |
| AI/ML | PyTorch, Scikit-learn, LangChain | GPU 서버 + EC2 |

## 서비스 구성
| 서비스 | 포트 | 담당 기능 |
|--------|------|-----------|
| Gateway | 80/443 | Nginx, API 라우팅, 프론트 정적 배포 |
| Ingestion | 5001 | MQTT 수집, WebSocket relay, Redis Streams Producer |
| State-Processor | 5002 | 센서 상태 처리, 이상 감지, State DB 관리 |
| Control | 5003 | 설비 제어 명령, Control DB 관리 |
| AI-Service | 5004 | 발전량/수요 예측, 운영 지원 AI, AI DB 관리 |
| DB-Writer | 5005 | 시계열 데이터 일괄 저장 (TimescaleDB Consumer) |

## 로컬 실행 방법
```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일의 모든 빈 값 채우기 (REDIS_PASSWORD, *_PASSWORD, MQTT_USER/PASSWORD, JWT_SECRET 등)

# 2. 환경변수 검증 (누락된 필수 값이 있으면 실패)
./infra/check_env.sh

# 3. 전체 서비스 실행 (한 방)
docker compose up -d --build
# stream-init 컨테이너가 자동으로 Redis Streams Consumer Group을 생성한 뒤,
# 모든 서비스가 순서대로 기동됩니다.
```

## Redis Streams 토픽 목록
| Stream 이름 | Producer | Consumer | 데이터 내용 |
|-------------|----------|----------|-------------|
| mg:sensor:data | Ingestion | State-Processor, AI-Service | MQTT 수집 원시 데이터 |
| mg:sensor:alert | Ingestion, State-Processor | State-Processor | 임계값 초과, 이상 감지 알림 |
| mg:control:cmd | Control | Ingestion | 설비 제어 명령 (on/off, 출력 조정) |
| mg:state:result | State-Processor | DB-Writer | 가공된 상태 데이터 |
| mg:ai:result | AI-Service | Control, DB-Writer | AI 예측/추천 결과 |
| mg:db:write | 전체 서비스 | DB-Writer | 시계열 저장 요청 |
| mg:emergency:event | Ingestion, State-Processor | State-Processor, Control, DB-Writer | 비상 이벤트 (Emergency Event Bus) |

## 브랜치 전략
| 브랜치 | 용도 | 규칙 |
|--------|------|------|
| master | 팀 통합 브랜치 | feature 브랜치들의 MR 대상 |
| feature/xxx | 기능 개발 | master에서 분기, 완료 후 master로 MR |

브랜치 네이밍: `feature/서비스명-기능명` (예: `feature/ingestion-mqtt-streams`)

## 주의사항
- .env 파일은 절대 GitLab에 올리지 말 것 (.gitignore에 포함됨)
- master 브랜치에 직접 푸시 금지
- 타 서비스 DB 직접 접근 금지 (API 호출 또는 Redis Streams 사용)
- Redis Streams 토픽 이름은 한번 정하면 변경 금지 (.env로 관리)

## 앱 ↔ 인프라 계약

**Flask 앱 엔트리포인트 계약**: 모든 서비스는 `app/main.py` 에 `app = Flask(__name__)` 로 노출한다.
- `docker-compose*.yml` 의 `environment.FLASK_APP` 은 `app.main:app` 로 고정
- 앱 구조 변경 시 (예: `create_app()` factory 전환, 파일 이동) `docker-compose*.yml` 의 `FLASK_APP` 값을 함께 갱신해야 함
- Dockerfile 은 런타임 환경만 정의 (Python 버전, port, healthcheck) — `FLASK_APP` 은 compose 단에서 주입
