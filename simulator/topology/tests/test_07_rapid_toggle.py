"""
시나리오 9: 선로 장애 빠른 반복 토글 — 시스템 안정성 검증

동일 선로를 FAULT → RESTORE 3사이클 반복해
매 복구 후 시뮬레이터가 정상 상태로 돌아오는지 확인한다.

커버하는 케이스:
  - 3회 연속 FAULT/RESTORE 후 comms_health, P 모두 정상 복귀
  - 마지막 사이클 종료 후 안정 상태(P>0, comms_health=ok) 유지

주의: FAULT_PROPAGATE_SEC 이내로 토글해도 retained 메시지가 덮어쓰이므로
      각 토글마다 FAULT_PROPAGATE_SEC 대기 후 검증한다.
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
EDGE_ID         = "test-rapid-solar"
DEVICE_ID       = "test-rapid-solar-01"
PEER_EDGE_ID    = "test-rapid-solar-peer"
PEER_DEVICE_ID  = "test-rapid-solar-peer-01"
TOPIC           = f"{PLANT_ID}/solar/{DEVICE_ID}/telemetry"
LINE_ID         = "test-line-rapid"
SW_ID           = "test-sw-rapid"

CYCLES    = 3
MSG_COUNT = 3


def run():
    cap = MqttCapture()
    cap.subscribe(TOPIC)
    results = []

    try:
        create_edge("solar", EDGE_ID, DEVICE_ID)
        create_edge("ess", PEER_EDGE_ID, PEER_DEVICE_ID, extra_device_fields=ESS_DEVICE_DEFAULTS)
        create_test_line(LINE_ID, EDGE_ID, PEER_EDGE_ID, switch_id=SW_ID)
        time.sleep(FAULT_PROPAGATE_SEC)
        print(f"\n[Scenario 9] 선로 장애 빠른 반복 토글 ({CYCLES}사이클) 테스트")

        # ─ 9-1: 초기 정상 상태 확인 ─────────────────────────────────────────
        name = "S9-1 초기 정상 상태 (P>0, comms_health=ok)"
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

        # ─ 사이클 반복: FAULT → RESTORE ──────────────────────────────────────
        for cycle in range(1, CYCLES + 1):
            # FAULT 주입
            fault_name = f"S9-{cycle*2} 사이클 {cycle}/FAULT → wire_fault"
            try:
                topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": True})
                time.sleep(FAULT_PROPAGATE_SEC)
                cap.clear()
                msgs = cap.collect(MSG_COUNT)
                assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
                log_result(fault_name, True)
                results.append((fault_name, True))
            except AssertionError as e:
                log_result(fault_name, False, str(e))
                results.append((fault_name, False))

            # RESTORE 복구
            restore_name = f"S9-{cycle*2+1} 사이클 {cycle}/RESTORE → ok"
            try:
                topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
                time.sleep(FAULT_PROPAGATE_SEC)
                cap.clear()
                msgs = cap.collect(MSG_COUNT)
                assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
                p = msgs[0]["payload"]["data"]["instantaneous"]["P"]
                log_result(restore_name, True, f"P={p:.2f}kW")
                results.append((restore_name, True))
            except AssertionError as e:
                log_result(restore_name, False, str(e))
                results.append((restore_name, False))

        # ─ 최종 안정 상태 확인 (추가 대기 없이 연속 수집) ────────────────────
        final_idx = CYCLES * 2 + 2
        name = f"S9-{final_idx} 최종 안정 상태 유지 (P>0, comms_health=ok)"
        try:
            cap.clear()
            # 3개 더 수집해 일시적 flickering이 없는지 확인
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            p_vals = [m["payload"]["data"]["instantaneous"]["P"] for m in msgs]
            log_result(name, True, f"P={p_vals[0]:.2f}kW (안정)")
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
