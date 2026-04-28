"""
시나리오 6: Load 시뮬레이터 wire_fault 테스트

커버하는 케이스:
  - 부하가 정상 소비 중 선로 FAULT → P=0, comms_health=wire_fault
  - 복구 → 정상 소비 재개
  - SWITCH OPEN으로도 동일 동작 확인
"""

import time
import traceback

from utils import (
    ESS_DEVICE_DEFAULTS, FAULT_PROPAGATE_SEC, PLANT_ID,
    MqttCapture, create_edge, create_test_line, cleanup_test_line,
    delete_edge, restore_topology, topo,
    assert_telemetry, log_result,
)

# 테스트 격리: 운영 device/line과 충돌하지 않도록 test-prefix 사용
EDGE_ID         = "test-load-fault"
DEVICE_ID       = "test-load-fault-01"
PEER_EDGE_ID    = "test-load-fault-peer"
PEER_DEVICE_ID  = "test-load-fault-peer-01"
TOPIC           = f"{PLANT_ID}/load/{DEVICE_ID}/telemetry"
LINE_ID         = "test-line-load-fault"
SW_ID           = "test-sw-load-fault"

MSG_COUNT = 3


def run():
    cap = MqttCapture()
    cap.subscribe(TOPIC)
    results = []

    try:
        create_edge("load", EDGE_ID, DEVICE_ID)
        create_edge("ess", PEER_EDGE_ID, PEER_DEVICE_ID, extra_device_fields=ESS_DEVICE_DEFAULTS)
        create_test_line(LINE_ID, PEER_EDGE_ID, EDGE_ID, switch_id=SW_ID)
        time.sleep(FAULT_PROPAGATE_SEC)

        print("\n[Scenario 6] Load LINE FAULT / SWITCH 테스트")

        # ─ 6-1: 정상 부하 소비 확인 ──────────────────────────────────────────
        name = "S6-1 Load 정상 소비 (P>0, comms_health=ok)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            p = msgs[0]["payload"]["data"]["instantaneous"]["P"]
            log_result(name, True, f"P={p:.2f}kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 6-2: LINE FAULT 주입 ──────────────────────────────────────────────
        name = "S6-2 LINE_FAULT 주입 후 P=0, comms_health=wire_fault"
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

        # ─ 6-3: 복구 ─────────────────────────────────────────────────────────
        name = "S6-3 LINE 복구 후 정상 소비 재개"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 6-4: SWITCH OPEN ──────────────────────────────────────────────────
        name = "S6-4 SWITCH_OPEN 후 P=0, comms_health=wire_fault"
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

        # ─ 6-5: SWITCH CLOSE ─────────────────────────────────────────────────
        name = "S6-5 SWITCH_CLOSE 후 정상 소비 재개"
        try:
            topo("PATCH", f"/api/switches/{SW_ID}", {"command": "CLOSE_SWITCH"})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

    except Exception as e:
        print(f"  [ERROR] 예외 발생: {e}")
        traceback.print_exc()
        results.append(("예외", False))
    finally:
        cleanup_test_line(LINE_ID)
        restore_topology()
        delete_edge(EDGE_ID)
        delete_edge(PEER_EDGE_ID)
        cap.stop()

    return results
