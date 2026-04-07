# SSAFY S305 - MG(마이크로그리드) 모니터링 시스템

## 프로젝트 개요
Vue.js + TypeScript 프론트엔드, FastAPI(Python) 백엔드 다중 서비스, MQTT 브로커, TimescaleDB, Redis Streams, AI/ML 파이프라인으로 구성된 마이크로그리드 모니터링 시스템.

## 아키텍처
| 레이어 | 구성요소 | 비고 |
|--------|----------|------|
| Web Server | Nginx (Reverse Proxy, HTTPS, WebSocket) | Gateway EC2 |
| Frontend | Vue.js + TypeScript | 정적 파일 배포 |
| Backend | FastAPI (Python) - 서비스별 분리 | EC2 4대 |
| IoT | MQTT Broker + WebSocket | 실시간 데이터 수집 |
| Database | TimescaleDB (PostgreSQL) - DB 4개 논리 분리 | RDS db.t3.micro |
| Cache/Event Bus | Redis (캐시) + Redis Streams (이벤트 버스) | Ingestion EC2 |
| AI/ML | PyTorch, Scikit-learn, LangChain, Airflow | GPU 서버 + EC2 |

## 서비스 구성
| 서비스 | 포트 | 담당 기능 |
|--------|------|-----------|
| Gateway | 80/443 | Nginx, API 라우팅, 프론트 정적 배포 |
| Monitoring | 8000 | 모니터링 조회, 제어, 운영로그, 사용자/권한 |
| Ingestion | 8001 | MQTT 수집, WebSocket relay, Redis Streams Producer |
| Forecast-AI | 8002 | 발전량/수요 예측, 운영 지원 AI, Streams Consumer |
| Report | 8003 | 리포트 생성, 시뮬레이션, Airflow, Streams Consumer |

## 로컬 실행 방법
```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에서 비밀번호 등 실제 값 채우기 (최소한 REDIS_PASSWORD 필수)

# 2. 전체 서비스 실행
docker compose up --build

# 3. Redis Streams Consumer Group 초기화 (최초 1회)
pip install redis
python infra/init_streams.py
```

## Redis Streams 토픽 목록
| Stream 이름 | Producer | Consumer | 데이터 내용 |
|-------------|----------|----------|-------------|
| mg:sensor:data | Ingestion | Monitoring, Forecast-AI | MQTT 수집 원시 데이터 |
| mg:sensor:alert | Ingestion, Monitoring | Monitoring | 임계값 초과, 이상 감지 알림 |
| mg:control:cmd | Monitoring | Ingestion | 설비 제어 명령 (on/off, 출력 조정) |
| mg:forecast:result | Forecast-AI | Monitoring, Report | AI 예측 결과 (발전량, 수요) |
| mg:report:trigger | Airflow(Report) | Report | 정기 리포트 생성 트리거 |

## 브랜치 전략
| 브랜치 | 용도 | 규칙 |
|--------|------|------|
| main | 배포 전용 | 직접 푸시 금지. MR만 허용 |
| develop | 팀 통합 브랜치 | feature 브랜치들의 MR 대상 |
| feature/xxx | 기능 개발 | develop에서 분기, 완료 후 develop으로 MR |

브랜치 네이밍: `feature/서비스명-기능명` (예: `feature/ingestion-mqtt-streams`)

## 주의사항
- .env 파일은 절대 GitLab에 올리지 말 것 (.gitignore에 포함됨)
- main 브랜치에 직접 푸시 금지
- 타 서비스 DB 직접 접근 금지 (API 호출 또는 Redis Streams 사용)
- Redis Streams 토픽 이름은 한번 정하면 변경 금지 (.env로 관리)
