# 포팅 매뉴얼 (AIEMS)

> SSAFY S14 자율 프로젝트 — 마이크로그리드 모니터링 시스템

## 목차

1. **Gitlab 소스 클론 이후 빌드 및 배포 문서**
    - 1.1 기술 스택 및 버전 정보
    - 1.2 빌드 시 사용되는 환경 변수 상세
    - 1.3 빌드 및 배포 절차
    - 1.4 배포 시 특이사항
    - 1.5 DB 접속 정보 및 주요 프로퍼티 정의 파일 목록
2. **프로젝트에서 사용하는 외부 서비스 정보**

---

# 1. Gitlab 소스 클론 이후 빌드 및 배포 문서

## 프로젝트 환경 개요

마이크로서비스 아키텍처. **5대 EC2 + 1대 Jenkins**(별도 인스턴스) 위에 Docker Compose로 prod/dev 환경을 분리 운영한다.

| 환경       | URL                                             | 비고                                      |
| ---------- | ----------------------------------------------- | ----------------------------------------- |
| 운영(Prod) | `https://power21.kr` / `https://www.power21.kr` | Cloudflare 프록시 → Gateway EC2 8080/8443 |
| 개발(Dev)  | 별도 공인 도메인 없음                           | Tailscale 또는 사설 IP + 포트 9080/9443   |

### EC2 구성 (총 6대)

| 역할            | 사설 IP       | 담당 서비스 (Prod)                    |
| --------------- | ------------- | ------------------------------------- |
| Gateway         | 172.31.37.96  | nginx 리버스 프록시, 프론트 정적 파일 |
| Ingestion       | 172.31.45.48  | MQTT 수집, Mosquitto, Redis           |
| State-Processor | 172.31.33.89  | 상태 처리, DB-Writer, Socket.IO       |
| Control + AI    | 172.31.34.123 | 제어, AI 예측 서비스                  |
| DB              | 172.31.44.52  | TimescaleDB, PostgreSQL (논리 3분리)  |
| Jenkins         | 172.26.0.25   | CI/CD 전용 (별도 VPC)                 |

**Prod/Dev는 같은 EC2에서 컨테이너 이름과 포트로 격리됨** (`app-*` vs `dev-*`, `--project-name dev`).

---

## 1.1 기술 스택 및 버전 정보

### 백엔드 (Python / Flask)

| 항목        | 버전 / 설정                                         |
| ----------- | --------------------------------------------------- |
| Language    | Python 3.10                                         |
| Base Image  | `python:3.10-slim` (모든 EMS 서비스 공통)           |
| Framework   | Flask 3.1.0                                         |
| API Spec    | flask-smorest 0.45.0 (Marshmallow 기반 스키마 검증) |
| WSGI        | gunicorn 21.2.0                                     |
| ORM/Driver  | psycopg2-binary 2.9.10, asyncpg 0.29.0              |
| Cache/Bus   | redis 5.0.4 (Redis Streams)                         |
| MQTT        | aiomqtt 2.3.0, paho-mqtt 2.1.0                      |
| WebSocket   | flask-socketio 5.3.6 (state-processor 한정)         |
| HTTP Client | requests 2.32.3, httpx 0.27.2                       |
| Metrics     | prometheus-flask-exporter 0.23.1                    |
| Timezone    | Asia/Seoul                                          |

서비스별 Dockerfile:

- `ems/ingestion/Dockerfile` (포트 5001)
- `ems/state-processor/Dockerfile` (5002)
- `ems/control/Dockerfile` (5003)
- `ems/ai/Dockerfile` (5004)
- `ems/db-writer/Dockerfile` (5005)

### 프론트엔드 (Vue 3 / Vite)

| 항목             | 버전                                |
| ---------------- | ----------------------------------- |
| Language         | TypeScript 5.7.2                    |
| Runtime (빌드)   | Node.js 20 (`node:20-alpine`)       |
| Framework        | Vue 3.5.13                          |
| Build Tool       | Vite 6.0.5                          |
| 타입 체크        | vue-tsc 2.2.0                       |
| Router           | Vue Router 4.5.0                    |
| State Management | Pinia 2.3.0                         |
| HTTP Client      | axios 1.7.9                         |
| Chart            | chart.js 4.5.1                      |
| Map              | maplibre-gl 5.24.0                  |
| Realtime         | socket.io-client 4.8.3              |
| i18n             | vue-i18n 9.14.1                     |
| CSS              | tailwindcss 3.4.16 + postcss 8.4.49 |

빌드 산출물: `frontend/dist/` → Gateway EC2의 `/home/ubuntu/app/frontend-dist/`에 배포

### 웹서버 / 게이트웨이 (nginx)

| 항목          | 버전 / 설정                                               |
| ------------- | --------------------------------------------------------- |
| Reverse Proxy | `nginx:1.25-alpine`                                       |
| TLS           | Cloudflare Origin Certificate                             |
| 인증서 경로   | `/etc/cloudflare/power21.kr.pem` + `.key`                 |
| Real IP       | `CF-Connecting-IP` 헤더 복구 (Cloudflare IP 화이트리스트) |
| Client Body   | 기본값 사용                                               |
| 환경별 conf   | `nginx.prod.conf` / `nginx.dev.conf`                      |

### 데이터베이스 / 미들웨어

| 항목        | 버전                                     |
| ----------- | ---------------------------------------- |
| TimescaleDB | `timescale/timescaledb:2.15.3-pg15`      |
| PostgreSQL  | `postgres:15.5`                          |
| Redis       | `redis:7.2-alpine` (AOF + 패스워드 인증) |
| MQTT Broker | `eclipse-mosquitto:2.0.18`               |
| 문자셋      | UTF-8                                    |

### AI / ML

| 항목              | 설정                                                                 |
| ----------------- | -------------------------------------------------------------------- |
| Language          | Python 3.10                                                          |
| Framework         | Flask + flask-smorest (다른 EMS 서비스와 동일)                       |
| Inference Backend | RunPod (GPU 서버, Live Satellite/Solar 모델)                         |
| 로컬 모델         | LightGBM (`kpx_5min_capacity_factor_lightgbm`, `solar_kpx_lightgbm`) |
| 모델 경로         | `/app/ems/ai/models/` (컨테이너 내부)                                |

### 인프라 / DevOps

| 항목            | 설정                                                                     |
| --------------- | ------------------------------------------------------------------------ |
| Container       | Docker + Docker Compose V2                                               |
| CI/CD           | Jenkins (별도 EC2 `172.26.0.25`)                                         |
| VCS             | GitLab (SSAFY) `https://lab.ssafy.com/s14-final/S14P31S305`              |
| Deploy Strategy | Blue/Green 미사용 — `docker compose up -d --build` 직접 교체             |
| 변경 감지       | 경로 기반 (`gateway/`, `ems/<service>/`, `frontend/`, `docker-compose*`) |
| Notification    | Mattermost (빌드 결과)                                                   |
| Edge Network    | Cloudflare (DNS + Tunnel + Origin Cert)                                  |
| Ops SSH         | Tailscale (tailnet `100.x.x.x`로 EC2 6대 메쉬)                           |

### IDE (권장)

| 항목              | 용도                        |
| ----------------- | --------------------------- |
| PyCharm / VS Code | 백엔드 (Python 3.10, Flask) |
| VS Code + Volar   | 프론트엔드 (Vue 3 + TS)     |

---

## 1.2 빌드 시 사용되는 환경 변수 상세

**보안 주의**: 실제 값은 Jenkins **Managed Files**로 관리. `.env` 파일은 git에 포함되지 않으며 배포 시점에만 EC2로 주입된다.

### Jenkins Managed Files

| File ID       | 종류        | 설명                     |
| ------------- | ----------- | ------------------------ |
| `ems-env`     | Config File | 운영(prod) 전체 환경변수 |
| `ems-env-dev` | Config File | 개발(dev) 전체 환경변수  |

### Prod 환경변수 (`ems-env`)

> Prod와 Dev는 **동일 EC2에서 다른 포트/데이터 디렉터리/비밀번호**로 격리 운영된다. 모든 비밀값(`*_PASSWORD`, `*_SECRET`)은 prod/dev가 완전히 다른 값으로 분리되어 있다.

#### TimescaleDB

| 변수명                    | 설명                 | Prod 값           | Dev 값                |
| ------------------------- | -------------------- | ----------------- | --------------------- |
| `TIMESCALE_HOST`          | 컨테이너 호스트명    | `timescaledb`     | `timescaledb`         |
| `TIMESCALE_PORT`          | 컨테이너 내부 포트   | `5432`            | `6432`                |
| `TIMESCALE_HOST_PORT`     | 호스트 노출 포트     | `5432`            | `6432`                |
| `TIMESCALE_DATA_DIR`      | EBS bind mount 경로  | `/data/timescale` | `/data/timescale-dev` |
| `TIMESCALE_DB`            | DB명                 | `timescale_db`    | `timescale_db`        |
| `TIMESCALE_USER`          | 일반 사용자명        | `timescale_user`  | `timescale_user`      |
| `TIMESCALE_PASSWORD`      | 일반 사용자 비밀번호 | (비밀값)          | (별도 비밀값)         |
| `TIMESCALE_ROOT_PASSWORD` | root 비밀번호        | (비밀값)          | (별도 비밀값)         |

#### PostgreSQL (논리 3분리: state, ai, control)

| 변수명                                             | 설명                | Prod 값                                    | Dev 값                        |
| -------------------------------------------------- | ------------------- | ------------------------------------------ | ----------------------------- |
| `POSTGRES_HOST`                                    | 컨테이너 호스트명   | `postgres`                                 | `postgres`                    |
| `POSTGRES_PORT`                                    | 컨테이너 내부 포트  | `5433`                                     | `6433`                        |
| `POSTGRES_HOST_PORT`                               | 호스트 노출 포트    | `5433`                                     | `6433`                        |
| `POSTGRES_DATA_DIR`                                | EBS bind mount 경로 | `/data-postgres/postgres`                  | `/data-postgres/postgres-dev` |
| `POSTGRES_ROOT_PASSWORD`                           | root 비밀번호       | (비밀값)                                   | (별도 비밀값)                 |
| `STATE_DB` / `STATE_USER` / `STATE_PASSWORD`       | state 논리 DB       | `state_write_db` / `state_user` / (비밀값) | 동일 명, 별도 비밀값          |
| `AI_DB` / `AI_USER` / `AI_PASSWORD`                | ai 논리 DB          | `ai_db` / `ai_user` / (비밀값)             | 동일 명, 별도 비밀값          |
| `CONTROL_DB` / `CONTROL_USER` / `CONTROL_PASSWORD` | control 논리 DB     | `control_db` / `control_user` / (비밀값)   | 동일 명, 별도 비밀값          |

#### Redis

| 변수명            | 설명               | Prod 값  | Dev 값        |
| ----------------- | ------------------ | -------- | ------------- |
| `REDIS_HOST`      | 컨테이너 호스트명  | `redis`  | `redis`       |
| `REDIS_PORT`      | 컨테이너 내부 포트 | `6379`   | `7379`        |
| `REDIS_HOST_PORT` | 호스트 노출 포트   | `6379`   | `7379`        |
| `REDIS_PASSWORD`  | 인증 비밀번호      | (비밀값) | (별도 비밀값) |

#### Redis Streams 토픽 (이벤트 버스)

| 변수명                   | 값                   |
| ------------------------ | -------------------- |
| `STREAM_SENSOR_DATA`     | `mg:sensor:data`     |
| `STREAM_SENSOR_ALERT`    | `mg:sensor:alert`    |
| `STREAM_CONTROL_CMD`     | `mg:control:cmd`     |
| `STREAM_STATE_RESULT`    | `mg:state:result`    |
| `STREAM_AI_RESULT`       | `mg:ai:result`       |
| `STREAM_DB_WRITE`        | `mg:db:write`        |
| `STREAM_EMERGENCY_EVENT` | `mg:emergency:event` |

#### MQTT

| 변수명                        | 설명               | Prod 값          | Dev 값                |
| ----------------------------- | ------------------ | ---------------- | --------------------- |
| `MQTT_BROKER_HOST`            | 브로커 호스트명    | `mqtt`           | `mqtt`                |
| `MQTT_BROKER_PORT`            | 컨테이너 내부 포트 | `1883`           | `2883`                |
| `MQTT_HOST_PORT`              | 호스트 노출 포트   | `1883`           | `2883`                |
| `MQTT_WS_HOST_PORT`           | WebSocket 포트     | `9001`           | `9091`                |
| `MQTT_USER` / `MQTT_PASSWORD` | 인증 정보          | `ems` / (비밀값) | `ems` / (별도 비밀값) |

#### 서비스 포트 (Flask)

| 변수명           | Prod | Dev  |
| ---------------- | ---- | ---- |
| `INGESTION_PORT` | 5001 | 6001 |
| `STATE_PORT`     | 5002 | 6002 |
| `CONTROL_PORT`   | 5003 | 6003 |
| `AI_PORT`        | 5004 | 6004 |
| `DB_WRITER_PORT` | 5005 | 6005 |

#### Gateway / nginx

| 변수명                | Prod              | Dev              |
| --------------------- | ----------------- | ---------------- |
| `GATEWAY_HTTP_PORT`   | 8080              | 9080             |
| `GATEWAY_HTTPS_PORT`  | 8443              | 9443             |
| `NGINX_CONF`          | `nginx.prod.conf` | `nginx.dev.conf` |
| `CLOUDFLARE_CERT_DIR` | `/etc/cloudflare` | `./certs`        |

#### API / 보안

| 변수명           | 설명                            | Prod / Dev               |
| ---------------- | ------------------------------- | ------------------------ |
| `API_SECRET_KEY` | Flask Secret Key (32바이트 hex) | **prod/dev 별도 비밀값** |
| `JWT_SECRET`     | JWT 서명 키 (32바이트 hex)      | **prod/dev 별도 비밀값** |

#### AI / 외부 서비스

| 변수명                    | 설명                                                                                         |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| `S305_STATE_API_BASE_URL` | AI → state-processor 호출용. Prod `http://172.31.33.89:5002`, Dev `http://172.31.33.89:6002` |
| `RUNPOD_KEY`              | RunPod 추론 서버 API 키 (비밀값)                                                             |
| `S305_OPENAI_ENABLED`     | OpenAI 사용 여부. **false** (미사용)                                                         |

> `JWT_SECRET`, `API_SECRET_KEY` 생성: `openssl rand -hex 32`

---

## 1.3 빌드 및 배포 절차

### EC2 초기 세팅 (최초 1회)

```bash
# 1. Docker / Compose 설치 (Ubuntu 22.04 기준)
sudo apt update && sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker ubuntu

# 2. (DB EC2만) EBS 마운트 디렉터리 준비
sudo mkdir -p /data/timescale /data/timescale-dev
sudo mkdir -p /data-postgres/postgres /data-postgres/postgres-dev
sudo chown -R 999:999 /data/timescale* /data-postgres/postgres*

# 3. (Gateway EC2만) Cloudflare Origin Certificate 배치
sudo mkdir -p /etc/cloudflare
sudo cp power21.kr.pem /etc/cloudflare/
sudo cp power21.kr.key /etc/cloudflare/
sudo chmod 600 /etc/cloudflare/*.key

# 4. Tailscale 설치 (운영 SSH용)
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --auth-key=<tskey-...>
```

### 로컬 전체 기동 (개발자 PC)

```bash
# 1. 환경변수 준비
cp .env.example .env
# 빈 값 모두 채움 (REDIS_PASSWORD, *_PASSWORD, MQTT_USER/PASSWORD, JWT_SECRET 등)

# 2. 필수 변수 검증
./infra/check_env.sh

# 3. 전체 서비스 기동
docker compose up -d --build
# stream-init 컨테이너가 Redis Streams Consumer Group 생성 후 정상 종료
# 이어서 모든 서비스가 의존성 순서대로 기동됨
```

### CI/CD 자동 배포 (Jenkins)

GitLab Webhook → Jenkins Pipeline 자동 트리거.

| 브랜치 / 이벤트     | 동작                                    |
| ------------------- | --------------------------------------- |
| `master` push       | **prod 배포** (5대 EC2 병렬)            |
| `master` 타겟 MR    | prod 배포                               |
| `ems` 브랜치 push   | dev 배포 (백엔드/인프라)                |
| `front` 브랜치 push | dev 프론트엔드 빌드 (frontend/ 변경 시) |

**경로 기반 변경 감지** (`Jenkinsfile:89-97`):

| 경로                        | 트리거 플래그                     |
| --------------------------- | --------------------------------- |
| `gateway/`                  | `CHANGED_GATEWAY`                 |
| `ems/ingestion/`            | `CHANGED_INGESTION`               |
| `ems/state-processor/`      | `CHANGED_STATE`                   |
| `ems/db-writer/`            | `CHANGED_DBWRITER`                |
| `ems/control/`              | `CHANGED_CONTROL`                 |
| `ems/ai/`                   | `CHANGED_AI`                      |
| `frontend/`                 | `CHANGED_FRONTEND`                |
| `docker-compose*`, `infra/` | `CHANGED_INFRA` (5대 모두 재배포) |

**파이프라인 단계**:

1. **Checkout** — 변경 브랜치 가져옴
2. **Detect Changes** — 경로 기반 플래그 세팅
3. **Verify Env** — `infra/check_env.sh`로 필수 변수 검증
4. **SonarQube Analysis** — 정적 분석
5. **Build (parallel)** — 변경된 서비스만 Docker 이미지 빌드
6. **Test (parallel)** — pytest (서비스별)
7. **Deploy (parallel)** — 5대 EC2 동시 배포
    - `configFileProvider`로 Managed File `ems-env` 가져와 `.env`로 scp
    - 서비스 코드 + compose 파일을 EC2로 scp (`/home/ubuntu/app/`)
    - `docker compose up -d --build --remove-orphans` 실행
    - 이미지/빌더 캐시 prune
8. **Frontend Deploy** (변경 시) — Node 빌드 → Gateway EC2의 `frontend-dist/` 갱신
9. **Mattermost 알림** — 성공/실패 결과 + 변경 서비스 목록

### 수동 배포 (Jenkins 미사용 시)

```bash
# 각 EC2에서 (예: gateway)
cd /home/ubuntu/app
git pull origin master
docker compose -f docker-compose.gateway.yml up -d --build --remove-orphans

# 또는 dev
cd /home/ubuntu/dev
docker compose --project-name dev -f docker-compose.gateway.yml up -d --build --remove-orphans
```

---

## 1.4 배포 시 특이사항

### 1) Blue/Green 미사용

재배포 시 `docker compose up -d --build`로 컨테이너를 직접 교체한다. `--build`로 새 이미지 빌드 → 변경 감지된 컨테이너만 재생성됨. 짧은 다운타임 발생 가능 (수 초). Stateful 컨테이너(DB, Redis, MQTT)는 설정이 동일하면 재생성하지 않아 무중단 유지.

### 2) Vue/Vite 빌드 시점 환경변수

Vite의 `VITE_*` 접두사 환경변수는 **빌드 시점에 번들에 정적 삽입**됨. 런타임 변경 불가. 환경변수 변경 시 `npm run build` 재실행 필요.

### 3) Cloudflare 프록시 전제

nginx.prod.conf는 클라이언트 IP를 `CF-Connecting-IP` 헤더에서 복구하도록 설정됨. Cloudflare를 우회해 직접 접근하면 클라이언트 IP가 Cloudflare CIDR로 잡힐 수 있음.

### 4) SG 정책 — EC2 간 통신

프로젝트 초기엔 SSAFY 공용 IP만 SSH 허용했으나, 현재는 **Tailscale**로 어디서든 SSH 가능. 단 EC2 간 내부 통신(예: AI → state-processor:5002)은 `ems-app-sg`의 인바운드 규칙에 명시되어야 함. VPC CIDR(`172.31.0.0/16`) 전체 허용을 권장.

### 5) 환경변수 미스매치 주의

코드는 다음 환경변수 이름을 기대한다 (혼동 자주 발생):

- AI → state: `S305_STATE_API_BASE_URL` (코드 기준, ems/ai/service/app/config.py:41)
- 단순 `STATE_PROCESSOR_URL`로 적으면 무시됨

### 6) Forecast 자동 실행 없음

AI 서비스에 내장 스케줄러가 없음. `POST /api/ai/forecast` 또는 `POST /api/ai/forecast/scheduled`를 **외부 cron**에서 주기적으로 호출해야 그래프 데이터가 채워진다. 현재 운영에서는 AI EC2의 crontab으로 매시 정각 호출.

### 7) DB 스키마 초기화는 Shell 스크립트

별도 마이그레이션 프레임워크 없음. `infra/init_postgres.sh`, `infra/init_timescale.sh`가 컨테이너 최초 기동 시 실행. 모두 `IF NOT EXISTS`로 멱등성 보장.

### 8) prod/dev 동일 EC2 운영

같은 EC2에서 prod(`app-*` 컨테이너 + 5xxx/8080 포트)와 dev(`dev-*` + 6xxx/9080)가 동시에 도는 구조. `--project-name dev` 옵션으로 컨테이너/네트워크/볼륨 자동 분리.

### 9) 시뮬레이터는 로컬 전용 자산

`simulator/`, `simulator/simulator-manager/`, `override.yml` 등은 로컬 테스트용. **git에 절대 커밋 금지**.

---

## 1.5 DB 접속 정보 및 주요 프로퍼티 정의 파일 목록

### DB / 미들웨어 접속 정보

| 항목                        | Prod                                    | Dev                               |
| --------------------------- | --------------------------------------- | --------------------------------- |
| TimescaleDB (컨테이너 내부) | `timescaledb:5432`                      | `timescaledb:6432`                |
| TimescaleDB (VPC 내부)      | `172.31.44.52:5432`                     | `172.31.44.52:6432`               |
| TimescaleDB DB / User       | `timescale_db` / `timescale_user`       | 동일 (별도 비밀번호)              |
| TimescaleDB 데이터 경로     | `/data/timescale`                       | `/data/timescale-dev`             |
| PostgreSQL (컨테이너 내부)  | `postgres:5433`                         | `postgres:6433`                   |
| PostgreSQL (VPC 내부)       | `172.31.44.52:5433`                     | `172.31.44.52:6433`               |
| PostgreSQL 논리 DB          | `state_write_db`, `ai_db`, `control_db` | 동일 (별도 비밀번호)              |
| PostgreSQL 데이터 경로      | `/data-postgres/postgres`               | `/data-postgres/postgres-dev`     |
| Redis (컨테이너 내부)       | `redis:6379`                            | `redis:7379`                      |
| Redis (VPC 내부)            | `172.31.45.48:6379`                     | `172.31.45.48:7379`               |
| MQTT Broker                 | `mqtt:1883` / `172.31.45.48:1883`       | `mqtt:2883` / `172.31.45.48:2883` |
| MQTT WebSocket              | `:9001`                                 | `:9091`                           |

> Docker volume이 아닌 **호스트 bind mount**로 데이터 영구화. EC2 재기동 시에도 데이터 유지. prod/dev는 디렉터리가 분리되어 있어 서로 영향 없음.

### PostgreSQL 논리 DB별 주요 테이블

| 논리 DB          | 테이블                                                                                                                                                   | 용도                           |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| `state_write_db` | `device_meta`, `comms_health_log`                                                                                                                        | 디바이스 레지스트리, 통신 상태 |
| `control_db`     | `control_policy`, `control_policy_history`, `topology_nodes/lines/switches`                                                                              | 제어 정책, 토폴로지            |
| `ai_db`          | `ai_forecast_run`, `ai_forecast_point`, `ai_forecast_actual`, `ai_forecast_latest_24h`, `ai_inference_event`, `ai_site_load_profile`, `ai_site_metadata` | 예측 실행/포인트/실적          |

### TimescaleDB 하이퍼테이블

| 테이블            | 용도               | 보존 정책                                       |
| ----------------- | ------------------ | ----------------------------------------------- |
| `sensor_data`     | 시계열 센서 측정값 | 1m/1h continuous aggregate, 7일 압축, 90일 보존 |
| `event_log`       | 알람/이벤트        | 30일 압축, 90일 보존                            |
| `control_history` | 제어 명령 감사     | 30일 압축, 180일 보존                           |

### 주요 설정 파일

| 경로                             | 설명                                                                      |
| -------------------------------- | ------------------------------------------------------------------------- |
| `.env.example`                   | 환경변수 템플릿 (실제 `.env`는 git 제외)                                  |
| `docker-compose.yml`             | 로컬 통합 기동용 (서비스 전체)                                            |
| `docker-compose.gateway.yml`     | Gateway EC2용                                                             |
| `docker-compose.ingestion.yml`   | Ingestion EC2용 (MQTT + Redis 포함)                                       |
| `docker-compose.state.yml`       | State-Processor + DB-Writer                                               |
| `docker-compose.control.yml`     | Control + AI                                                              |
| `docker-compose.db.yml`          | TimescaleDB + PostgreSQL                                                  |
| `docker-compose.monitoring.yml`  | Prometheus + Grafana + Promtail                                           |
| `docker-compose.exporters.yml`   | node-exporter, cadvisor, mqtt-exporter, redis-exporter, postgres-exporter |
| `docker-compose.cicd.yml`        | Jenkins 서버용 (별도 EC2)                                                 |
| `gateway/nginx.prod.conf`        | 운영 nginx 라우팅 + Cloudflare 설정                                       |
| `gateway/nginx.dev.conf`         | 개발 nginx                                                                |
| `infra/init_postgres.sh`         | PostgreSQL 3개 논리 DB 생성 + 스키마                                      |
| `infra/init_timescale.sh`        | TimescaleDB 하이퍼테이블 + 압축 정책                                      |
| `infra/init_streams.py`          | Redis Streams Consumer Group 초기화                                       |
| `infra/mosquitto/mosquitto.conf` | MQTT 브로커 설정                                                          |
| `infra/check_env.sh`             | 필수 환경변수 검증 스크립트                                               |
| `Jenkinsfile`                    | CI/CD 파이프라인 (단일 파일)                                              |
| `ems/ai/service/app/config.py`   | AI 서비스 환경변수 매핑 (`S305_*` 접두)                                   |

### EC2별 컨테이너 배치 (실측 기준)

#### Gateway EC2 (172.31.37.96 / `100.95.93.41`)

| 컨테이너                                                  | 호스트 포트 | 내부 포트  | 환경 |
| --------------------------------------------------------- | ----------- | ---------- | ---- |
| `app-gateway-1`                                           | 8080, 8443  | 8080, 8443 | prod |
| `dev-gateway-1`                                           | 9080, 9443  | 8080, 8443 | dev  |
| `promtail`, `nginx-exporter`, `node-exporter`, `cadvisor` | —           | —          | 공통 |

#### Ingestion EC2 (172.31.45.48 / `100.126.227.114`)

| 컨테이너                                                                   | 호스트 포트 | 내부 포트  | 환경 |
| -------------------------------------------------------------------------- | ----------- | ---------- | ---- |
| `app-ingestion-1`                                                          | 5001        | 5001       | prod |
| `dev-ingestion-1`                                                          | 6001        | 5001       | dev  |
| `app-mqtt-1`                                                               | 1883, 9001  | 1883, 9001 | prod |
| `dev-mqtt-1`                                                               | 2883, 9091  | 1883, 9001 | dev  |
| `app-redis-1`                                                              | 6379        | 6379       | prod |
| `dev-redis-1`                                                              | 7379        | 6379       | dev  |
| `mqtt-exporter`, `redis-exporter`, `promtail`, `node-exporter`, `cadvisor` | —           | —          | 공통 |

#### State EC2 (172.31.33.89 / `100.76.217.5`)

| 컨테이너                                | 호스트 포트 | 내부 포트 | 환경 |
| --------------------------------------- | ----------- | --------- | ---- |
| `app-state-processor-1`                 | 5002        | 5002      | prod |
| `dev-state-processor-1`                 | 6002        | 5002      | dev  |
| `app-db-writer-1`                       | 5005        | 5005      | prod |
| `dev-db-writer-1`                       | 6005        | 5005      | dev  |
| `promtail`, `node-exporter`, `cadvisor` | —           | —         | 공통 |

#### Control + AI EC2 (172.31.34.123 / `100.109.88.92`)

| 컨테이너                                | 호스트 포트 | 내부 포트 | 환경 |
| --------------------------------------- | ----------- | --------- | ---- |
| `app-control-1`                         | 5003        | 5003      | prod |
| `dev-control-1`                         | 6003        | 5003      | dev  |
| `app-ai-1`                              | 5004        | 5004      | prod |
| `dev-ai-1`                              | 6004        | 5004      | dev  |
| `promtail`, `node-exporter`, `cadvisor` | —           | —         | 공통 |

#### DB EC2 (172.31.44.52 / `100.98.2.82`)

| 컨테이너                                                     | 호스트 포트 | 내부 포트 | 환경 |
| ------------------------------------------------------------ | ----------- | --------- | ---- |
| `app-timescaledb-1`                                          | 5432        | 5432      | prod |
| `dev-timescaledb-1`                                          | 6432        | 5432      | dev  |
| `app-postgres-1`                                             | 5433        | 5432      | prod |
| `dev-postgres-1`                                             | 6433        | 5432      | dev  |
| `postgres-exporter`, `promtail`, `node-exporter`, `cadvisor` | —           | —         | 공통 |

#### Jenkins EC2 (172.26.0.25 / `100.124.158.59`)

| 컨테이너                            | 호스트 포트                      | 용도      |
| ----------------------------------- | -------------------------------- | --------- |
| Jenkins (`docker-compose.cicd.yml`) | (내부 only / 리버스 프록시 경유) | CI/CD     |
| SonarQube                           | (내부 only)                      | 정적 분석 |

### nginx 라우팅 요약 (`gateway/nginx.prod.conf`)

| 외부 경로                     | 내부 upstream                         |
| ----------------------------- | ------------------------------------- |
| `/api/ingestion/`             | `172.31.45.48:5001` (ingestion)       |
| `/api/state/`, `/api/plants/` | `172.31.33.89:5002` (state-processor) |
| `/api/control/`               | `172.31.34.123:5003` (control)        |
| `/api/ai/`                    | `172.31.34.123:5004` (ai)             |
| `/api/db/`                    | `172.31.33.89:5005` (db-writer)       |
| `/socket.io/`                 | state-processor (WebSocket upgrade)   |
| `/ws/`                        | ingestion (WebSocket)                 |
| `/`                           | 정적 파일 (`/var/www/html`)           |

---

# 2. 프로젝트에서 사용하는 외부 서비스 정보

## 2.1 RunPod (AI 추론 GPU 서버)

| 항목          | 설명                                                                                 |
| ------------- | ------------------------------------------------------------------------------------ |
| 서비스        | [RunPod](https://www.runpod.io) — GPU 서버리스 추론                                  |
| 용도          | Live Satellite 기반 태양광 발전량 예측 (`v10` 체크포인트)                            |
| 가입 경로     | RunPod 계정 생성 → Serverless Endpoint 배포                                          |
| 이미지        | `ems/ai/runpod/Dockerfile.inference` (모델 가중치 포함)                              |
| Handler       | `ems/ai/runpod/handler.py`                                                           |
| Client        | `ems/ai/scripts/runpod_client.py`                                                    |
| 관련 환경변수 | `RUNPOD_KEY`, 옵션 yaml `ems/ai/configs/ops/operational_solar_forecast_example.yaml` |
| 호출 시점     | `/api/ai/forecast` 호출 시 `solar_backend=live_satellite` 분기에서 실행              |

## 2.2 Cloudflare (DNS + Tunnel + TLS)

| 항목          | 설명                                                                               |
| ------------- | ---------------------------------------------------------------------------------- |
| 도메인        | `power21.kr`, `www.power21.kr` (Cloudflare 등록)                                   |
| 용도          | DNS, CDN, TLS termination, Origin Certificate 발급                                 |
| 인증서        | Cloudflare Origin Certificate (만료 15년) → Gateway nginx에 마운트                 |
| 인증서 경로   | `/etc/cloudflare/power21.kr.pem` + `power21.kr.key`                                |
| Tunnel        | cloudflared 컨테이너로 Gateway EC2와 Cloudflare Edge 연결 (인바운드 80/443 미오픈) |
| Tunnel 라우트 | `power21.kr` → `http://gateway:8080`                                               |
| Tunnel 토큰   | Jenkins/직접 발급 후 `.env`에 `CF_TUNNEL_TOKEN` (옵션)                             |

## 2.3 Tailscale (운영 SSH)

| 항목            | 설명                                                         |
| --------------- | ------------------------------------------------------------ |
| 서비스          | [Tailscale](https://tailscale.com) — WireGuard 기반 mesh VPN |
| 용도            | 개발자/팀원 PC ↔ EC2 6대 SSH 접속                            |
| Tailnet IP 예시 | gateway `100.95.93.41`, db `100.98.2.82` 등                  |
| MagicDNS        | 활성 — `ssh ubuntu@ip-172-31-37-96` 형태로 접근 가능         |
| ACL             | `grants: *:*:*` 기본 + 일반 sshd + pem 키 인증               |
| 운영 효과       | AWS SG에서 22번 외부 노출 차단해도 tailnet으로 접근 가능     |

## 2.4 GitLab (SSAFY)

| 항목        | 설명                                                                   |
| ----------- | ---------------------------------------------------------------------- |
| 저장소      | `https://lab.ssafy.com/s14-final/S14P31S305`                           |
| 브랜치 정책 | `master` (운영), `ems` (백엔드/인프라 작업), `front` (프론트엔드 작업) |
| Webhook     | Jenkins 파이프라인 트리거 (push, MR 이벤트)                            |

## 2.5 Jenkins (CI/CD)

| 항목          | 설명                                                |
| ------------- | --------------------------------------------------- |
| 위치          | 별도 EC2 (사설 IP `172.26.0.25`, 별도 VPC)          |
| 이미지        | `jenkins/jenkins:lts-jdk21`                         |
| 플러그인      | GitLab, Config File Provider, SSH Agent, Mattermost |
| Credential    | `ec2-ssh-key` (5대 EC2 + 자기 자신 공통 pem)        |
| Managed Files | `ems-env`, `ems-env-dev`                            |
| 알림          | Mattermost Webhook (성공/실패)                      |

## 2.6 모니터링 / 관측성 (내부)

자체 호스팅, 외부 SaaS 미사용.

### 메트릭 / 로그 수집 스택 (`docker-compose.monitoring.yml`)

| 컴포넌트     | 컨테이너 이름  | 용도             |
| ------------ | -------------- | ---------------- |
| Prometheus   | `prometheus`   | 메트릭 수집/저장 |
| Grafana      | `grafana`      | 대시보드         |
| Alertmanager | `alertmanager` | 알림 라우팅      |
| Loki         | `loki`         | 로그 저장        |

### 익스포터 / 에이전트 (`docker-compose.exporters.yml`, 각 EC2에 배포)

| 컴포넌트          | 컨테이너 이름       | 용도                              |
| ----------------- | ------------------- | --------------------------------- |
| node-exporter     | `node-exporter`     | 호스트 메트릭 (CPU/메모리/디스크) |
| cAdvisor          | `cadvisor`          | 컨테이너 메트릭                   |
| redis-exporter    | `redis-exporter`    | Redis 메트릭                      |
| postgres-exporter | `postgres-exporter` | PostgreSQL/TimescaleDB 메트릭     |
| nginx-exporter    | `nginx-exporter`    | nginx 메트릭                      |
| mqtt-exporter     | `mqtt-exporter`     | Mosquitto 메트릭                  |
| promtail          | `promtail`          | 로그 수집 → Loki 전송             |

---

## 부록 — 빠른 명령 모음

### SSH 접속 (Tailscale 경유)

```bash
ssh -i ems-ec2-key.pem ubuntu@100.95.93.41   # gateway
ssh -i ems-ec2-key.pem ubuntu@100.126.227.114 # ingestion
ssh -i ems-ec2-key.pem ubuntu@100.76.217.5    # state
ssh -i ems-ec2-key.pem ubuntu@100.109.88.92   # control + ai
ssh -i ems-ec2-key.pem ubuntu@100.98.2.82     # db
ssh -i ems-ec2-key.pem ubuntu@100.124.158.59  # jenkins
```

### 상태 확인

```bash
docker ps                                              # 컨테이너 목록
docker compose -f docker-compose.<service>.yml ps      # 서비스별
docker logs app-<service>-1 --tail 100 -f              # 로그 추적
```

### Forecast 수동 트리거 (cron 보조용)

```bash
curl -s -X POST -H 'Content-Type: application/json' \
  -d "{
    \"site_id\":\"PLANT-ALPHA\",
    \"trigger_source\":\"manual\",
    \"region\":\"대전시\",
    \"latitude\":36.35,
    \"longitude\":127.38,
    \"installed_capacity_kw\":100.0,
    \"periods\":24,
    \"frequency_hours\":1.0,
    \"start_time\":\"$(date -u +%Y-%m-%dT%H:00:00Z)\",
    \"solar_backend\":\"capacity_factor\"
  }" \
  http://172.31.34.123:5004/api/ai/forecast
```

### DB 직접 조회

```bash
# PostgreSQL (ai_db 예시)
docker exec app-postgres-1 psql -U ai_user -d ai_db -c "SELECT COUNT(*) FROM ai_forecast_run;"

# TimescaleDB
docker exec app-timescaledb-1 psql -U timescale_user -d timescale_db -c "\dt"
```
