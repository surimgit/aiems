"""
시나리오 5: Diesel 시뮬레이터 wire_fault 테스트

커버하는 케이스:
  - 디젤 발전기 기동(RUNNING) 중 선로 FAULT → P=0, comms_health=wire_fault
  - 복구 → 정상 발전 재개

주의: diesel은 OFF 상태에서 시작. 기동 명령 전송 후 STARTUP_TIME(30s) 대기 필요.
"""

import json
import time
import traceback

from utils import (
    EDGE_STARTUP_SEC, FAULT_PROPAGATE_SEC, PLANT_ID,
    MqttCapture, create_edge, delete_edge, restore_topology, topo,
    assert_telemetry, log_result,
)

EDGE_ID   = "test-diesel-fault"
DEVICE_ID = "diesel-01"
TOPIC     = f"{PLANT_ID}/diesel/{DEVICE_ID}/telemetry"
CMD_TOPIC = f"{PLANT_ID}/diesel/{DEVICE_ID}/command"
LINE_ID   = "line-diesel01-ess01"

# diesel 기동 시간 30s + 여유
DIESEL_STARTUP_WAIT = 35

MSG_COUNT = 3


def _start_command() -> dict:
    return {
        "command_id": "test-diesel-start-001",
        "command_type": "start",
        "payload": {},
    }


def _set_power_command(kw: float) -> dict:
    return {
        "command_id": "test-diesel-power-001",
        "command_type": "set_power",
        "payload": {"target_p_kw": kw},
    }


def run():
    cap = MqttCapture()
    cap.subscribe(TOPIC)
    results = []

    try:
        create_edge("diesel", EDGE_ID, DEVICE_ID)

        # ── 기동 명령 전송 ────────────────────────────────────────────────────
        time.sleep(3)
        cap.publish(CMD_TOPIC, _start_command())
        cap.publish(CMD_TOPIC, _set_power_command(500.0))
        print(f"  [setup] diesel 기동 명령 전송. RUNNING 대기 ({DIESEL_STARTUP_WAIT}s)...")
        time.sleep(DIESEL_STARTUP_WAIT)

        print("\n[Scenario 5] Diesel LINE FAULT 테스트")

        # ─ 5-1: RUNNING 상태 확인 ─────────────────────────────────────────────
        name = "S5-1 Diesel RUNNING 정상 상태 (P>0, comms_health=ok)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            p_values = [m["payload"]["data"]["instantaneous"]["P"] for m in msgs]
            comms = [m["payload"]["data"]["status"]["comms_health"] for m in msgs]
            assert all(c == "ok" for c in comms), f"comms_health: {comms}"
            assert any(p > 0 for p in p_values), f"P>0 기대, got: {p_values}"
            log_result(name, True, f"P={p_values[0]:.1f}kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 5-2: LINE FAULT 주입 ──────────────────────────────────────────────
        name = "S5-2 LINE_FAULT 주입 후 P=0, comms_health=wire_fault (mode=running 유지)"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": True})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
            # status.operating_mode 가 running 유지인지 확인
            modes = [m["payload"]["data"]["status"].get("operating_mode") for m in msgs]
            log_result(name, True, f"mode={modes[0]}")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 5-3: 선로 복구 ────────────────────────────────────────────────────
        name = "S5-3 LINE 복구 후 P>0, comms_health=ok"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            p_values = [m["payload"]["data"]["instantaneous"]["P"] for m in msgs]
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok")
            assert any(p > 0 for p in p_values), f"복구 후 P>0 기대, got: {p_values}"
            log_result(name, True, f"P={p_values[0]:.1f}kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

    except Exception as e:
        print(f"  [ERROR] 예외 발생: {e}")
        traceback.print_exc()
        results.append(("예외", False))
    finally:
        restore_topology()
        delete_edge(EDGE_ID)
        cap.stop()

    return results
