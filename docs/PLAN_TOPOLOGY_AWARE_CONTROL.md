# 토폴로지 인식 EMS 제어 — 작업 플랜

작성: 2026-05-07
근거: `task_018_topology_aware_ems_power_flow_control.md` + 현재 코드 검증
대상: `ems/control` (주), `ems/state-processor` (보조), `simulator/ess-simulator` (선택)

---

## 1. 결론 한 줄

EMS control 의 dispatchability 판단이 SOC 만 보고 토폴로지 / wire_fault / 연결 그래프를 무시해서, **고립된 ESS 에 명령 반복 발행 + 디젤 미기동 + load 공급 부족 미감지** 가 동시에 발생한다.

---

## 2. 현재 검증된 코드 사실

| 항목 | 위치 | 상태 |
|---|---|---|
| `ess_can_discharge = any(SOC > threshold)` | `ems/control/app/domain/rules/diesel.py:27` | SOC 만 봄 — wire_fault / 토폴로지 무시 |
| ESS command guard 없음 | `ems/control/app/domain/rules/ess.py` | 고립된 ESS 에도 charge/discharge 발행 |
| state-processor wire_fault 처리 없음 | `ems/state-processor/app/api.py` | comms_health 그대로 통과만 |
| 폐루프 검증 → EVT-N-005 발행 | `ems/control/app/adapters/mqtt_commander.py` | 결과는 잡지만 *원인* 모름 |
| topology graph 빌드 로직 없음 | (전체 control) | 전무 |

---

## 3. 핵심 통찰

**문제가 3겹이다:**

1. **연결성 무시** — control 이 토폴로지 그래프를 모름
2. **dispatchability ≠ SOC** — "방전 가능"의 정의가 SOC 만으로는 부족함. comms_health, operating_mode, 토폴로지 연결성 모두 봐야 함
3. **현재 공급 ≠ 명령 가능** — standby diesel 은 현재 공급 0이지만 명령 후보임. 단순 P > 0 필터링하면 fail-safe 가 깨짐

→ **`current_contributing_resources`** 와 **`dispatchable_*_devices`** 를 분리해야 한다.

---

## 4. 작업 단위 (Phase 별)

### Phase A — Topology Graph Helper (작은 순수 함수)

**목적:** 토폴로지 응답 → 연결 그래프 → resource 별 reachable set.

**파일 (신규):** `ems/control/app/domain/topology_graph.py`

**입력:** `TopologyDto` (state-processor 의 `/api/plants/{site_id}/topology` 응답)

**출력:**
- `resource_id → node_id` map
- `node_id → resource_id` map
- 유효 선로 기준 adjacency list (양방향)
- `resource_id → set[reachable resource_id]` (해당 자원과 연결된 모든 자원)
- `is_connected_to_any_load(resource_id) -> bool` 헬퍼

**유효 선로 조건:**
```
line.status == "NORMAL"
AND (line 의 모든 switch.position == "CLOSED")
```

**제외:** `OPEN`, `FAULT`, `BLOCKED`, `UNKNOWN`, `TRANSITIONING`.

**테스트:** 순수 함수라 단위 테스트 가능. dict 입력 → dict/set 출력.

**예상 코드량:** 80~120 lines.

---

### Phase B — Topology Snapshot 적재 경로

**목적:** control loop 가 매 iteration 마다 토폴로지를 알 수 있게.

**선택지:**
1. ✅ **HTTP 호출** — state-processor 의 `/api/plants/{site_id}/topology` 를 control 이 매 iteration 호출
2. control 이 직접 control_db 조회 + Redis state 융합 (state-processor 와 코드 중복)
3. MQTT topology retained topic 구독

**추천: 1번.** 이유:
- 단일 진실 (state-processor 가 융합 책임)
- 코드 중복 없음
- 1초 주기 수십 개 노드는 부하 적음
- 캐싱 (1초 TTL) 으로 더 줄일 수 있음

**파일 (신규):** `ems/control/app/adapters/topology_reader.py`

**책임:**
- state-processor URL 호출 (env: `STATE_PROCESSOR_URL`, default `http://state-processor:5002`)
- 응답 캐시 (1초 TTL)
- 실패 시 last-known fallback (또는 빈 그래프 반환)

**예상 코드량:** 50~80 lines.

---

### Phase C — Dispatchability 계산 분리

**목적:** SOC 단독 판정 제거. flow 객체에 `dispatchable_*` 필드 추가.

**수정 파일:** `ems/control/app/domain/power_flow.py`

**변경:**
- `compute(states, topology_graph)` 시그니처 변경 — graph 추가 인자
- 결과 dict 에 추가:
  - `dispatchable_ess_devices: list[dict]` — SOC 충분 + ok + 비-fault + load 와 연결
  - `dispatchable_diesel_devices: list[dict]` — comms ok + load 와 연결 (fault 제외)
  - `current_contributing_*` 는 기존 필드 유지

**구현 의사 코드:**

```python
def _is_dispatchable_ess(ess, graph, soc_low):
    if (ess["SOC"] or 0) <= soc_low: return False
    if ess.get("comms_health") != "ok": return False
    mode = (ess.get("operating_mode") or "").lower()
    if mode in ("fault", "error"): return False
    return graph.is_connected_to_any_load(ess["device_id"])

def _is_dispatchable_diesel(diesel, graph):
    if diesel.get("comms_health") != "ok": return False
    mode = (diesel.get("operating_mode") or "").lower()
    if mode in ("fault", "error"): return False
    return graph.is_connected_to_any_load(diesel["device_id"])
```

**예상 코드량:** 50~80 lines.

---

### Phase D — Diesel Rule 보정 (즉시 임팩트)

**수정 파일:** `ems/control/app/domain/rules/diesel.py`

**변경 (line 27):**

```python
# Before
ess_can_discharge = any(
    (e["SOC"] or 0) > diesel_start_soc for e in flow["ess_devices"]
)

# After
ess_can_discharge = bool(flow.get("dispatchable_ess_devices"))
```

**효과:**
- ESS 가 wire_fault 거나 토폴로지 고립이면 `dispatchable_ess_devices` 가 비어있음
- → `ess_can_discharge = False`
- → `net_power < 0` 일 때 디젤 start 발행
- **즉시 디젤 미기동 문제 해결**

**예상 코드량:** 5~10 lines (한 줄 변경 + 검증).

---

### Phase E — ESS Rule 가드 (명령 반복 방지)

**수정 파일:** `ems/control/app/domain/rules/ess.py`

**변경:**
- 매 ESS 자원에 대해 명령 발행 전 `dispatchable` 체크
- 비-dispatchable 이면 skip + 로그
- (선택) skip 사유를 Redis 또는 메모리에 기록해서 동일 사유 반복 로그 억제

**예시:**
```python
for ess in flow["ess_devices"]:
    if ess not in flow["dispatchable_ess_devices"]:
        print(f"[control] skip {ess['device_id']} command: not dispatchable "
              f"(comms={ess.get('comms_health')}, isolated={...})")
        continue
    # 기존 로직
```

**예상 코드량:** 30~50 lines.

---

### Phase F — Load Deficit Component 계산

**수정 파일:** `ems/control/app/domain/power_flow.py`

**변경:**
- 단일 net_power 외에 **load 별 component deficit** 도 계산
- `flow["component_deficits"] = [{load_id, deficit_kw, reachable_resources}, ...]`

**현재 단일 plant 단일 load 라 효과는 미미하지만, 코드 구조는 미리 잡아둠.**

**예상 코드량:** 60~100 lines.

**우선순위 낮음** — Phase G 까지 끝나면 진행.

---

### Phase G — ESS Simulator 상태 계약 보정 (선택)

**수정 파일:** `simulator/ess-simulator/core/command_handler.py` (또는 ess.py)

**변경:**
- 모든 연결 선로가 OPEN/FAULT 일 때 charge/discharge command 수신 시 `rejected` ACK 반환
- 또는 `accepted` 후 standby 유지 (정책 결정 필요)

**권장:** `rejected` — control 이 잘못된 명령 발행을 빠르게 인지.

**예상 코드량:** 40~80 lines.

**우선순위:** Phase E 후. simulator 변경이라 별도 PR.

---

### Phase H — 이벤트 / 로그 강화 (마지막)

**수정 파일:**
- `ems/control/app/domain/rules/safety.py` 또는 신규 `topology.py`

**추가 이벤트:**
- `EVT-N-016 LINE_BLOCKED` (이미 정의됨, 미발행)
- `EVT-E-007 LINE_FAULT` (이미 정의됨, 미발행)
- (선택) `RESOURCE_ISOLATED`, `LOAD_SUPPLY_DEFICIT` 신규

**제외 시나리오:** 동일 알람 반복 발행 — 5분 디바운스 권장.

**예상 코드량:** 60~100 lines.

---

## 5. 작업 우선순위

| Phase | 작업 | 임팩트 | 의존성 |
|---|---|---|---|
| A | topology_graph 헬퍼 | 인프라 | 없음 |
| B | topology_reader (HTTP 캐시) | 인프라 | A |
| **C** | **dispatchability 분리** | **★ 핵심** | A, B |
| **D** | **diesel rule 한 줄 변경** | **★★★ 즉시 효과** | C |
| E | ESS rule guard | ★★ | C |
| F | component deficit | ★ | C |
| G | ESS simulator 보정 | ★ | (별도) |
| H | 이벤트 / 로그 | ★ | C |

**최소 동작 라인:** A → B → C → D
→ 이 4개만 끝내도 디젤 미기동 + 명령 반복 둘 다 해결됨 (D 만으로도 디젤 문제 해결).

---

## 6. 테스트 시나리오 (task_018 §7 기반)

각 Phase 끝나면 아래 시나리오로 검증:

### T1. ESS 고립 테스트
```bash
# sw-solar01-ess01, sw-diesel01-ess01, sw-ess01-load01 OPEN
curl -X POST http://localhost:5003/api/control/operator-commands \
  -d '{"site_id":"PLANT-ALPHA","device_id":"sw-ess01-load01","resource_type":"SWITCH","action":"OPEN_SWITCH","requested_by":"test"}'
```
**기대:** ESS discharge 명령 중단, control 로그에 skip reason.

### T2. Diesel Fallback 테스트
ESS 고립 + load 부족 → 디젤 start 발행 확인.
```bash
docker logs s14p31s305-ems-control-1 --tail 50 | grep -i "diesel.*start"
```

### T3. 복구 테스트
모든 스위치 CLOSE → 정상 상태 복귀.

### T4. Solar 고립 테스트
solar 측 스위치 OPEN → solar 출력이 net_power 계산에서 제외되는지.

---

## 7. 안전 장치 / 회귀 방지

### 7.1 단위 테스트 (Phase A)
`ems/control/tests/test_topology_graph.py` 신규:
- 빈 토폴로지
- 단일 플랜트 정상 그래프
- 한 라인 OPEN
- 모든 라인 OPEN (완전 고립)
- 양방향 / 환형 토폴로지

### 7.2 통합 테스트
T1~T4 시나리오를 pytest 또는 shell script 로 자동화.

### 7.3 관찰 가능성
- control 로그에 매 iteration `dispatchable_ess=N, dispatchable_diesel=M, isolated_resources=[...]` 출력
- TUI 또는 대시보드에서 dispatchability 상태 시각화 (선택)

---

## 8. 범위 제외 (task_018 §10 기반)

❌ frontend 수정
❌ gateway/nginx 수정
❌ ai-service 수정
❌ topology_switches 스키마 대규모 변경
❌ flow_kw 실제 전력 흐름 계산 (flow_kw 는 표시용 0 유지)
❌ alarm ACK API 통일 (별도 task)

---

## 9. 결정 사항 (2026-05-07 확정)

| # | 결정 | 적용 방식 |
|---|---|---|
| Q1 | ESS isolated 시 ACK = `rejected` | Phase G 에서 ess-simulator command_handler 보정. 우선순위 낮음 (EMS 측 명령 차단으로 1차 해결). |
| Q2 | topology HTTP 실패 시 **last-known + 30초 제한** | 30초 내: 캐시 사용 / 30초 초과: 빈 그래프 + WARNING 로그. 30초는 STATE_TTL 과 일치. |
| Q3 | line:switch = **1:N 지원** | 그래프 헬퍼는 line 의 모든 switch 가 CLOSED 일 때만 통전. 시드는 현재처럼 1:1 유지. |
| Q4 | `comms_health` 는 **`ok` 만** dispatchable | `stale` / `wire_fault` / `unknown` 모두 제외. 단순 규칙으로 디버깅 쉬움. |
| Q5 | 운영자 명령은 dispatchable 체크 **통과** | 자동 룰만 안전 게이트. operator-commands 는 그대로. 시뮬레이터/장비가 거절하면 ACK 에 reflected. |

---

## 10. 예상 일정

| Phase | 시간 |
|---|---|
| A (graph helper) | 1~2시간 |
| B (topology_reader) | 1시간 |
| C (dispatchability) | 1~2시간 |
| D (diesel rule) | 30분 |
| E (ESS guard) | 1시간 |
| F (component deficit) | 2~3시간 |
| G (ESS simulator) | 2시간 |
| H (events) | 1~2시간 |
| 단위/통합 테스트 | 2~3시간 |

**최소 동작 (A+B+C+D):** 약 4~6시간
**전체:** 약 12~18시간

---

## 11. 한 줄 우선순위 요약

> **A → B → C → D 만 먼저 끝내면 디젤 미기동 + 명령 반복 양쪽 해결.**
> E ~ H 는 안정성 / 시뮬레이터 정합 / 이벤트 강화로 순차 진행.
