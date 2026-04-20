# 로컬 개발 환경 가이드

## 사전 준비

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 설치
- [DBeaver Community](https://dbeaver.io/download/) 설치 (DB 클라이언트, 선택사항)
- Git 설치

---

## 1. 프로젝트 클론

```bash
git clone https://lab.ssafy.com/s14-final/S14P31S305.git
cd S14P31S305
```

---

## 2. 환경 변수 설정

`.env.example`을 복사해서 `.env` 파일을 만들어주세요.

```bash
cp .env.example .env
```

`.env` 파일을 열고 아래 값을 참고하여 채워주세요. 패스워드/시크릿 값은 팀 노션 또는 인프라 담당자에게 문의하세요.

```env
# ===== TimescaleDB (시계열 데이터 전용) =====
TIMESCALE_HOST=timescaledb
TIMESCALE_PORT=5432
TIMESCALE_DB=timescale_db
TIMESCALE_USER=timescale_user
TIMESCALE_PASSWORD=<인프라 담당자 문의>
TIMESCALE_ROOT_PASSWORD=<인프라 담당자 문의>

# ===== PostgreSQL (state_write / ai / control DB 논리 분리) =====
POSTGRES_HOST=postgres
POSTGRES_PORT=5433
POSTGRES_ROOT_PASSWORD=<인프라 담당자 문의>

STATE_DB=state_write_db
STATE_USER=state_user
STATE_PASSWORD=<인프라 담당자 문의>

AI_DB=ai_db
AI_USER=ai_user
AI_PASSWORD=<인프라 담당자 문의>

CONTROL_DB=control_db
CONTROL_USER=control_user
CONTROL_PASSWORD=<인프라 담당자 문의>

# ===== Redis =====
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<인프라 담당자 문의>

# ===== Redis Streams 토픽 =====
STREAM_SENSOR_DATA=mg:sensor:data
STREAM_SENSOR_ALERT=mg:sensor:alert
STREAM_CONTROL_CMD=mg:control:cmd
STREAM_STATE_RESULT=mg:state:result
STREAM_AI_RESULT=mg:ai:result
STREAM_DB_WRITE=mg:db:write

# ===== MQTT =====
MQTT_BROKER_HOST=mqtt
MQTT_BROKER_PORT=1883

# ===== API =====
API_SECRET_KEY=<인프라 담당자 문의>
JWT_SECRET=<인프라 담당자 문의>
```

---

## 3. 인프라 실행

### 전체 실행 (모든 서비스)

```bash
docker compose up -d
```

### DB만 실행 (백엔드 개발 시 추천)

```bash
docker compose up timescaledb postgres -d
```

### DB + Redis + MQTT 실행

```bash
docker compose up timescaledb postgres redis mqtt -d
```

### 종료

```bash
docker compose down
```

### DB 데이터 초기화 (완전 리셋)

```bash
docker compose down -v
docker compose up timescaledb postgres -d
```

---

## 4. DB 접속 정보

DB는 **2개 컨테이너**로 분리되어 있습니다.

### TimescaleDB (시계열 데이터 전용)

| 항목 | 값 |
| ---- | --- |
| 컨테이너 | timescaledb |
| 호스트 포트 | 5432 |
| DB명 | timescale_db |
| 유저 | timescale_user |
| 용도 | DB-Writer 서비스가 센서 시계열 데이터 저장 |

### PostgreSQL (서비스 DB, 3개 논리 분리)

| 서비스 | DB명 | 유저 | 호스트 포트 |
| ------ | ---- | ---- | ---- |
| State-Processor | state_write_db | state_user | 5433 |
| AI-Service | ai_db | ai_user | 5433 |
| Control | control_db | control_user | 5433 |
| 관리자 | postgres | postgres | 5433 |

### 터미널에서 접속

```bash
# TimescaleDB
docker exec -it s14p31s305-timescaledb-1 psql -U timescale_user -d timescale_db

# PostgreSQL (예: state_write_db)
docker exec -it s14p31s305-postgres-1 psql -U state_user -d state_write_db
```

### DBeaver에서 접속

1. `Ctrl+Shift+N` → PostgreSQL 선택
2. 접속 정보 입력:
    - Host: `localhost`
    - Port: `5432` (TimescaleDB) 또는 `5433` (PostgreSQL)
    - Database: 자기 서비스 DB명
    - Username: 자기 서비스 유저
    - Password: 자기 서비스 패스워드
3. "Show all databases" 체크해야 DB 전체 보임
4. Test Connection → 완료

### TimescaleDB 확장 활성화

TimescaleDB 컨테이너는 `init_timescale.sh`에서 자동으로 확장을 설치합니다. 수동 실행 불필요.

---

## 5. 서비스 포트 정보

| 서비스 | 포트 | 설명 |
| ------ | ---- | ---- |
| Gateway (Nginx) | 80 | API 진입점 |
| Ingestion | 5001 | MQTT 수집, WebSocket |
| State-Processor | 5002 | 상태 처리 |
| Control | 5003 | 설비 제어 |
| AI-Service | 5004 | AI 예측 |
| DB-Writer | 5005 | 시계열 저장 |
| TimescaleDB | 5432 | 시계열 DB |
| PostgreSQL | 5433 | 서비스 DB (state/ai/control) |
| Redis | 6379 | 캐시 + Streams |
| MQTT | 1883 | 디바이스 데이터 수집 |
| MQTT WebSocket | 9001 | MQTT 웹소켓 |

---

## 6. 헬스체크

서비스 실행 후 정상 동작 확인:

```bash
curl http://localhost:5001/health   # Ingestion
curl http://localhost:5002/health   # State-Processor
curl http://localhost:5003/health   # Control
curl http://localhost:5004/health   # AI-Service
curl http://localhost:5005/health   # DB-Writer
```

정상 응답 예시:

```json
{ "status": "ok", "service": "ingestion" }
```

---

## 7. 자주 쓰는 명령어

```bash
# 실행 중인 컨테이너 확인
docker compose ps

# 특정 서비스 로그 보기
docker compose logs -f ingestion

# 특정 서비스만 재시작
docker compose restart ingestion

# Redis 접속
docker exec -it s14p31s305-redis-1 redis-cli -a redis1234

# MQTT 메시지 테스트 (mosquitto_pub 설치 필요)
mosquitto_pub -h localhost -p 1883 -t "test/topic" -m "hello"
```

---

## 주의사항

- `.env` 파일은 git에 올라가지 않습니다 (`.gitignore`에 포함)
- DB 데이터는 Docker 볼륨에 저장되므로, 컨테이너 종료 후에도 유지됩니다
- 완전 초기화하려면 `docker compose down -v` 사용 (볼륨 삭제)
- `postgres`라는 기본 DB가 보이는데 이건 시스템 기본 DB이므로 사용하지 마세요
