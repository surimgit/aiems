"""
시나리오 1~3: Solar 시뮬레이터 wire_fault 테스트

커버하는 케이스:
  1. LINE_FAULT  주입 → P=0, comms_health=wire_fault → 복구 → 정상
  2. SWITCH_OPEN → P=0, comms_health=wire_fault → CLOSE → 정상
  3. ISOLATE_LINE(운영자 차단) → P=0 → RESTORE_LINE → 정상
"""

import time
import traceback

from utils import (
    FAULT_PROPAGATE_SEC, PLANT_ID,
    MqttCapture, create_edge, delete_edge, restore_topology, topo,
    assert_telemetry, log_result,
)

EDGE_ID   = "test-solar-fault"
DEVICE_ID = "solar-01"
TOPIC     = f"{PLANT_ID}/solar/{DEVICE_ID}/telemetry"
LINE_ID   = "line-solar01-ess01"
SW_ID     = "sw-solar01-ess01"

MSG_COUNT = 4  # 검증에 사용할 메시지 수


def run():
    cap = MqttCapture()
    cap.subscribe(TOPIC)
    results = []

    try:
        # ── 엣지 기동 ──────────────────────────────────────────────────────────
        create_edge("solar", EDGE_ID, DEVICE_ID)

        # ═══════════════════════════════════════════════════════════════════════
        # Scenario 1: LINE FAULT 주입 / 복구
        # ═══════════════════════════════════════════════════════════════════════
        print("\n[Scenario 1] LINE FAULT 주입")
        name = "S1-1 정상 상태 확인 (LINE NORMAL)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            log_result(name, True, f"P={msgs[0]['payload']['data']['instantaneous']['P']:.2f} kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        name = "S1-2 LINE_FAULT 주입 후 P=0, comms_health=wire_fault"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": True})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        name = "S1-3 LINE 복구 후 정상 복귀"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            log_result(name, True, f"P={msgs[0]['payload']['data']['instantaneous']['P']:.2f} kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ═══════════════════════════════════════════════════════════════════════
        # Scenario 2: SWITCH OPEN / CLOSE
        # ═══════════════════════════════════════════════════════════════════════
        print("\n[Scenario 2] SWITCH OPEN / CLOSE")
        name = "S2-1 SWITCH_OPEN 후 P=0, comms_health=wire_fault"
        try:
            topo("PATCH", f"/api/switches/{SW_ID}", {"command": "OPEN_SWITCH"})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        name = "S2-2 SWITCH_CLOSE 후 정상 복귀"
        try:
            topo("PATCH", f"/api/switches/{SW_ID}", {"command": "CLOSE_SWITCH"})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            log_result(name, True, f"P={msgs[0]['payload']['data']['instantaneous']['P']:.2f} kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ═══════════════════════════════════════════════════════════════════════
        # Scenario 3: 운영자 ISOLATE / RESTORE
        # ═══════════════════════════════════════════════════════════════════════
        print("\n[Scenario 3] 운영자 ISOLATE / RESTORE")
        name = "S3-1 ISOLATE_LINE 후 P=0, comms_health=wire_fault"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"command": "ISOLATE_LINE"})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        name = "S3-2 RESTORE_LINE 후 정상 복귀"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"command": "RESTORE_LINE"})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            log_result(name, True, f"P={msgs[0]['payload']['data']['instantaneous']['P']:.2f} kW")
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
