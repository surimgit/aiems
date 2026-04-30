# EMS Master 통합 작업 계획서

> 시점: 2026-04-28
> 작업자: 사용자(EMS 코드 담당) + Claude
> 기준 폴더: `c:/ems/S14P31S305-master/`

---

## 1. 배경

- **인프라 담당자**가 master 브랜치에 5대 EC2 분산 배포용 골격을 잡아둠
  - `docker-compose.{db,gateway,ingestion,state,control}.yml` 5개
  - `infra/` 안에 init script 골격 (테이블 생성 부분은 우리가 채워야 함)
  - `ems/{서비스}/app/main.py`는 깡통 placeholder
- **우리 ems 브랜치**에 완성된 EMS 코드가 있음 (ingestion / state-processor / control)
- **우리 작업** = 우리 EMS 코드를 master 인프라 구조에 맞춰 이식하는 것

---

## 2. 결정된 아키텍처 (문서 + 아키텍처.png 기준)

### 2.1 EC2 배치

```
Gateway EC2     → gateway (nginx, port 8080)
Ingestion EC2   → ingestion + redis + mqtt + stream-init
State EC2       → state-processor + db-writer
Control EC2     → control + ai-service
DB EC2          → postgres + timescaledb
```

### 2.2 DB 분리 (문서 06-infra/database.md §3)

| 데이터 | 저장소 | 비고 |
| --- | --- | --- |
| sensor_data (telemetry) | TimescaleDB | hypertable, 압축/보존 |
| event_log (event) | TimescaleDB | hypertable, 30d 압축, 90d 보존 |
| control_history (command_result) | TimescaleDB | hypertable, 30d 압축, 180d 보존 |
| control_policy + history | PostgreSQL `control_db` | 운영자 조정 + 트리거 자동 기록 |
| topology_nodes/lines/switches | PostgreSQL `control_db` | 단선도 (시드는 simulator-manager 동적) |
| device_meta | PostgreSQL `state_write_db` | 등록 device 목록 + last_seen_at |
| comms_health_log | PostgreSQL `state_write_db` | 통신 두절/복구 이력 |
| ai_meta | PostgreSQL `ai_db` | AI 팀 영역 (우리 작업 X) |

### 2.3 INSERT 책임 (문서 04-services/db-writer.md)

**DB Writer가 모든 저장의 단일 게이트.**

```
state-processor → Redis stream publish (ems:state, ems:meta 등)
control         → Redis stream publish (ems:command-result 등)
                       ↓
                  DB Writer 가 stream consumer
                       ↓
                  TimescaleDB / PostgreSQL INSERT
```

→ state-processor / control 자체는 **DB INSERT 안 함**.
**예외:** control_policy 같은 운영자 조정은 control이 직접 UPDATE (운영자 API 경로).

### 2.4 Redis Streams 토픽

- `ems:normal` — 일반 telemetry (ingestion → state-processor)
- `ems:emergency` — 긴급 이벤트 (ingestion → state-processor / control)
- `ems:state` — state 계산 결과 (state-processor → DB Writer)
- 추가 예정: `ems:command-result`, `ems:meta`

---

## 3. 작업 영역 분담

| 영역 | 담당 |
| --- | --- |
| EMS 코드 (ingestion / state-processor / control) | 사용자 |
| DB 스키마 init script | 우리 함께 (이번 작업) |
| db-writer 신규 서비스 | 누구? (인프라 담당자? 우리?) |
| ai-service | AI 팀 |
| gateway nginx | 인프라 담당자 (이미 작성됨) |
| compose 5개 | 인프라 담당자 (이미 작성됨) |
| mosquitto entrypoint/acl | 인프라 담당자 (이미 작성됨) |
| 시뮬레이터 → master 통합 | 사용자 |

---

## 4. 진행 상태

### Phase 0 — 어제 완료한 것

- [x] `ems/ingestion/app/` 우리 코드 이식 (import 경로, Redis/MQTT 인증)
- [x] `ems/state-processor/app/` 우리 코드 이식
- [x] `ems/control/app/` 우리 코드 이식
- [x] 각 서비스 `config.py` 환경변수 매핑 (TIMESCALE_*, STATE_*, CONTROL_*)

> 다만 EMS 코드는 사용자 영역이라 추후 인프라 확정 후 재조정 필요.

### Phase A — DB 스키마 init script (현재 진행 중)

- [x] **A1. `infra/init_postgres.sh` 1차 작성** — control_db 테이블 + state_write_db.event_log
- [x] **A2. `infra/init_timescale.sh` 1차 작성** — sensor_data만
- [x] **A3. 재조정 완료** ✅
  - init_postgres.sh: event_log/control_history 제거, device_meta + comms_health_log 추가
  - init_timescale.sh: event_log + control_history hypertable 추가 (30d 압축, 90/180d 보존)

### Phase B — 코드 측 수정 (DB Writer 단일 게이트 적용) ✅ 완료

- [x] **B1.** state-processor config.py — TimescaleDB SELECT 용 (변경 없음, 이미 OK)
- [x] **B2.** state-processor DB INSERT 제거
       - `adapters/db_writer.py` 삭제
       - `domain/aggregator.py` 삭제 (db-writer 가 자체 보유)
       - `stream_consumer.py` 단순화 — emergency consume 제거, normal 만 처리
       - mg:state:result publish 는 기존 state_publisher.py 그대로 활용
- [x] **B3.** control control_history INSERT/UPDATE 제거
       - `adapters/db_writer.py` 재작성 — write 는 mg:db:write (kind=command) publish, read 만 직접 connection
       - mqtt_commander 는 기존 메서드 시그니처 그대로 호환 (insert_command/update_ack/mark_verified/get_command)
       - `api.py` operator command INSERT 도 mg:db:write publish 로 교체
- [x] **B4.** control event_log INSERT 제거
       - `adapters/event_publisher.py` 재작성 — DB pool 제거, severity 분기로 stream 발행만
       - CRITICAL → mg:emergency:event, WARNING/INFO → mg:db:write (kind=event)
- [x] **B5.** 알람 조회 API — 그대로 유지 (TimescaleDB SELECT, config.py 가 이미 가리킴)
- [x] **B6.** 알람 ack API 압축 chunk UPDATE 실패 캐치 — try/except 추가 후 410 Gone 응답

### Phase C — db-writer 신규 작성 (담당 = 우리) ✅ 완료

- [x] **C1.** Redis stream consumer 작성 (mg:state:result / mg:emergency:event / mg:db:write)
- [x] **C2.** TimescaleDB INSERT (sensor_data / event_log / control_history)
- [x] **C3.** PostgreSQL INSERT (device_meta / comms_health_log)
- [x] **C4.** 1초 batch flush 로직 (WindowAggregator 이식)
- [x] **C5.** Flask app + /health (Redis/Timescale/Postgres 3종 체크)

### Phase D — 로컬 통합 compose (담당 = 우리)

- [ ] **D1.** `docker-compose.local.yml` 신규 작성 — 단일 호스트에서 모든 서비스 통합 기동
- [ ] **D2.** `gateway/nginx.local.conf` 신규 작성 — Docker hostname 기반 upstream
- [ ] **D3.** `.env.example` 갱신 — compose 5개가 요구하는 변수명으로 새 작성

### Phase E — 검증

- [ ] **E1.** `docker compose -f docker-compose.local.yml up -d` 빌드 통과
- [ ] **E2.** 각 서비스 `/health` endpoint 응답 확인
- [ ] **E3.** simulator → ingestion → stream → state-processor → db-writer → DB 흐름 검증
- [ ] **E4.** control 명령 → MQTT → simulator → ack → 폐루프 검증

---

## 5. 우리가 다음 손볼 파일 (Phase A3 즉시 작업)

### 5.1 `infra/init_postgres.sh`

**control_db 부분 변경:**
- ❌ `control_history` 테이블 제거 (TimescaleDB로)
- ✅ `control_policy` + `control_policy_history` + 트리거 유지
- ✅ `topology_nodes/lines/switches` 유지 (시드는 simulator-manager가 동적)
- ✅ 정책 seed 19개 유지

**state_write_db 부분 변경:**
- ❌ `event_log` 제거 (TimescaleDB로)
- ❌ control_user에게 부여한 GRANT 제거 (이제 불필요)
- ✅ 신규: `device_meta` 테이블
- ✅ 신규: `comms_health_log` 테이블

**ai_db:** 비워둠 (AI 팀 영역)

### 5.2 `infra/init_timescale.sh`

**sensor_data:** 그대로 유지 (테이블, hypertable, 1m/1h 집계, 압축 7d, 보존 90d)

**신규 추가:**
- `event_log` 테이블 + hypertable + 인덱스
- `event_log` 압축 정책 (30d) + 보존 정책 (90d)
- `control_history` 테이블 + hypertable + 인덱스
- `control_history` 압축 정책 (30d) + 보존 정책 (180d)

---

## 6. 환경변수 매핑 (compose ↔ .env ↔ init script)

> 사용자가 추가한 `.env` 파일은 구버전이라 무시.
> compose 파일 (`docker-compose.db.yml` 등)이 기대하는 변수가 정답.

| 변수 | 사용처 | 비고 |
| --- | --- | --- |
| `POSTGRES_ROOT_PASSWORD` | postgres 컨테이너 root | |
| `STATE_DB`, `STATE_USER`, `STATE_PASSWORD` | state_write_db | state-processor 사용 |
| `AI_DB`, `AI_USER`, `AI_PASSWORD` | ai_db | AI 팀 |
| `CONTROL_DB`, `CONTROL_USER`, `CONTROL_PASSWORD` | control_db | control 사용 |
| `TIMESCALE_ROOT_PASSWORD` | timescaledb 컨테이너 root | |
| `TIMESCALE_DB`, `TIMESCALE_USER`, `TIMESCALE_PASSWORD` | timescale_db | db-writer / state-processor SELECT |
| `REDIS_PASSWORD` | redis 인증 | |
| `MQTT_USER`, `MQTT_PASSWORD` | mqtt 인증 | acl.template과 연동 |
| `API_SECRET_KEY`, `JWT_SECRET` | Flask 인증 | |

---

## 7. 확정 사항 (인프라 담당자 답변, 2026-04-28)

- [x] **db-writer = 우리(EMS 담당) 작성** — `app/main.py` 안의 stream consumer + INSERT 로직만 채움. Dockerfile/healthcheck/compose 편입은 인프라가 이미 잡아둠.
- [x] **시뮬레이터 master 통합 = 별도 PR로 분리** — 이번 master 통합 PR에는 묶지 않음. 우리는 천천히 진행.
- [x] **gateway nginx.prod.conf의 EC2 IP = prod 의도 그대로** — 우리는 별도 `nginx.local.conf`를 로컬 통합 compose와 함께 작성.
- [x] **알람 ack API = A안 채택** — TimescaleDB 압축 정책(30d) 이내 알람만 ack 가능. 30d 이상은 압축 chunk라 UPDATE 실패 → API에서 캐치 후 "오래된 알람은 ack 불가" 응답. 운영 시점 B안(별도 PostgreSQL ack 테이블 분리) 재검토.
- [x] **로컬 통합 compose = 옵션 C 선택** — 별도 `docker-compose.local.yml` 신규 작성. prod 5개 compose는 절대 건드리지 않음.

### 7.1 추가 작업 (답변에서 발견)

- [ ] **`.env.example` 우리가 갱신** — 현재 .env는 구버전. compose 5개가 요구하는 변수명(TIMESCALE_*, STATE_*, CONTROL_*, AI_*, MQTT_USER/PASSWORD 등)으로 새로 작성.
- [ ] **인프라 EBS 분리 PR 머지 후 rebase** — 인프라 담당자가 PostgreSQL EBS 100GB 분리 작업 중(`/data/postgres` → `/data-postgres/postgres`). 머지되면 우리 작업 위에 rebase. 그러나 사용자가 "천천히 MR 넣을 예정"이라 큰 충돌 없을 듯.

### 7.2 절대 건드리지 말 것

- `docker-compose.{db,gateway,ingestion,state,control}.yml` — Jenkins prod 배포 깨짐
- `Jenkinsfile`
- `infra/mosquitto/{entrypoint.sh, acl.template, mosquitto.conf}` — 인프라 담당자 영역

---

## 8. 다음 액션

**즉시:**
1. Phase A3 — init_postgres.sh, init_timescale.sh 재조정 (이 문서 §5 대로)
2. 검증 — bash 문법 체크

**그 다음:**
3. 인프라 담당자에게 §7 보류 사항 한꺼번에 질문
4. 답변 받으면 Phase B 또는 Phase C 결정

---

## 9. 메모 / 결정 이력

- **2026-04-28** — DB Writer 단일 게이트 결정 (문서 04-services/db-writer.md 기준)
- **2026-04-28** — event_log를 TimescaleDB로 (시계열, hypertable + 압축)
- **2026-04-28** — control_history를 TimescaleDB로 (command_result = 시계열)
- **2026-04-28** — state_write_db에 device_meta + comms_health_log 추가 결정
- **2026-04-28** — Topology 시드 INSERT는 simulator-manager가 동적 등록하므로 init script에서 제거
- **2026-04-28** — 인프라 담당자 답변 수령. db-writer/시뮬레이터/gateway/알람 ack/로컬 compose 분담 확정.
- **2026-04-28** — 알람 ack: A안 (30d 이내만 ack 가능, API에서 에러 응답)
- **2026-04-28** — 로컬 통합 compose: 옵션 C (별도 docker-compose.local.yml) → 결과적으로 인프라가 이미 `docker-compose.yml`로 작성해놨음. 우리 추가 작업 없음.
- **2026-04-29** — Redis Stream 이름을 인프라 명명규약(`mg:*`)으로 통일. `ems:normal/emergency/state` → `mg:sensor:data/emergency:event/state:result`. consumer group도 `state-processor-group` → `state-group`. (init_streams.py와 호환)
- **2026-04-29** — Phase D는 인프라가 이미 `docker-compose.yml` + `gateway/nginx.conf` + `.env.example` 모두 작성. 우리는 검증만.
- **2026-04-29** — Phase C(db-writer) 완료. mg:state:result/mg:emergency:event/mg:db:write 통합 consumer.
- **2026-04-29** — Phase B 완료. state-processor / control 의 모든 직접 DB INSERT 제거. db-writer 단일 게이트로 통합.
- **2026-04-29** — `mg:db:write` envelope kind 필드 정의: `command` / `event` / `comms` 3종.
