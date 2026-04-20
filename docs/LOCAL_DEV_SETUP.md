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
# ===== DB 설정 =====
MONITORING_DB_HOST=postgres
MONITORING_DB_PORT=5432
MONITORING_DB_NAME=monitoring_db
MONITORING_DB_USER=monitoring_user
MONITORING_DB_PASSWORD=<인프라 담당자 문의>

INGESTION_DB_HOST=postgres
INGESTION_DB_PORT=5432
INGESTION_DB_NAME=ingestion_db
INGESTION_DB_USER=ingestion_user
INGESTION_DB_PASSWORD=<인프라 담당자 문의>

FORECAST_DB_HOST=postgres
FORECAST_DB_PORT=5432
FORECAST_DB_NAME=forecast_db
FORECAST_DB_USER=forecast_user
FORECAST_DB_PASSWORD=<인프라 담당자 문의>

REPORT_DB_HOST=postgres
REPORT_DB_PORT=5432
REPORT_DB_NAME=report_db
REPORT_DB_USER=report_user
REPORT_DB_PASSWORD=<인프라 담당자 문의>

# ===== PostgreSQL =====
POSTGRES_PASSWORD=<인프라 담당자 문의>

# ===== Redis =====
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<인프라 담당자 문의>

# ===== Redis Streams 토픽 =====
STREAM_SENSOR_DATA=mg:sensor:data
STREAM_SENSOR_ALERT=mg:sensor:alert
STREAM_CONTROL_CMD=mg:control:cmd
STREAM_FORECAST_RESULT=mg:forecast:result
STREAM_REPORT_TRIGGER=mg:report:trigger

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
docker compose up postgres -d
```

### DB + Redis + MQTT 실행

```bash
docker compose up postgres redis mqtt -d
```

### 종료

```bash
docker compose down
```

### DB 데이터 초기화 (완전 리셋)

```bash
docker compose down -v
docker compose up postgres -d
```

---

## 4. DB 접속 정보

TimescaleDB (PostgreSQL 15) 기반이며, 서비스별로 DB가 분리되어 있습니다.

| 서비스     | DB명          | 유저            | 패스워드           | 포트 |
| ---------- | ------------- | --------------- | ------------------ | ---- |
| Monitoring | monitoring_db | monitoring_user | 인프라 담당자 문의 | 5432 |
| Ingestion  | ingestion_db  | ingestion_user  | 인프라 담당자 문의 | 5432 |
| Forecast   | forecast_db   | forecast_user   | 인프라 담당자 문의 | 5432 |
| Report     | report_db     | report_user     | 인프라 담당자 문의 | 5432 |
| 관리자     | postgres      | postgres        | 인프라 담당자 문의 | 5432 |

### 터미널에서 접속

```bash
# 예: monitoring_db 접속
docker exec -it s14p31s305-postgres-1 psql -U monitoring_user -d monitoring_db
```

### DBeaver에서 접속

1. `Ctrl+Shift+N` → PostgreSQL 선택
2. 접속 정보 입력:
    - Host: `localhost`
    - Port: `5432`
    - Database: 자기 서비스 DB명 (예: `monitoring_db`)
    - Username: 자기 서비스 유저 (예: `monitoring_user`)
    - Password: 자기 서비스 패스워드 (예: `monitoring_pw`)
3. "Show all databases" 체크해야 DB 4개 한번에 보임
4. Test Connection → 완료

### TimescaleDB 확장 활성화

각 DB에서 최초 1회 실행해주세요.

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
```

---

## 5. 서비스 포트 정보

| 서비스          | 포트 | 설명                 |
| --------------- | ---- | -------------------- |
| Gateway (Nginx) | 80   | API 진입점           |
| Monitoring      | 8000 | 관제/상태 API        |
| Ingestion       | 8001 | 데이터 수집          |
| Forecast-AI     | 8002 | AI 예측              |
| Report          | 8003 | 리포트               |
| PostgreSQL      | 5432 | TimescaleDB          |
| Redis           | 6379 | 캐시 + Streams       |
| MQTT            | 1883 | 디바이스 데이터 수집 |
| MQTT WebSocket  | 9001 | MQTT 웹소켓          |

---

## 6. 헬스체크

서비스 실행 후 정상 동작 확인:

```bash
# 브라우저 또는 curl로 확인
curl http://localhost:8000/health   # Monitoring
curl http://localhost:8001/health   # Ingestion
curl http://localhost:8002/health   # Forecast-AI
curl http://localhost:8003/health   # Report
```

정상 응답 예시:

```json
{ "status": "ok", "service": "monitoring" }
```

---

## 7. 자주 쓰는 명령어

```bash
# 실행 중인 컨테이너 확인
docker compose ps

# 특정 서비스 로그 보기
docker compose logs -f monitoring

# 특정 서비스만 재시작
docker compose restart monitoring

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
