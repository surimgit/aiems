"""
시나리오 8: ESS 방전(discharge) 중 wire_fault 테스트

커버하는 케이스:
  - ESS 방전 모드에서 선로 FAULT → P=0, comms_health=wire_fault
  - wire_fault 중에도 operating_mode=discharge 유지 (모드 초기화 금지)
  - 복구 → comms_health=ok, 방전 재개 (P>0)

주의: ESS 방전 시 P > 0 (양수 = 방전), 충전 시 P < 0 (음수 = 충전)
"""

import time
import traceback

from utils import (
    FAULT_PROPAGATE_SEC, PLANT_ID, ESS_DEVICE_DEFAULTS,
    MqttCapture, create_edge, delete_edge, restore_topology, topo,
    assert_telemetry, log_result,
)

EDGE_ID   = "test-ess-discharge"
DEVICE_ID = "ess-01"
TOPIC     = f"{PLANT_ID}/ess/{DEVICE_ID}/telemetry"
CMD_TOPIC = f"{PLANT_ID}/ess/{DEVICE_ID}/command"
LINE_ID   = "line-diesel01-ess01"

MSG_COUNT = 5


def _discharge_command() -> dict:
    return {
        "command_id": "test-ess-discharge-001",
        "command_type": "ess_mode",
        "expires_in_sec": 300.0,
        "payload": {"mode": "discharge", "target_power_kw": 20.0},
    }


def run():
    cap = MqttCapture()
    cap.subscribe(TOPIC)
    results = []

    try:
        create_edge("ess", EDGE_ID, DEVICE_ID, extra_device_fields=ESS_DEVICE_DEFAULTS)

        # ── 방전 명령 전송 ────────────────────────────────────────────────────
        time.sleep(2)
        cap.publish(CMD_TOPIC, _discharge_command())
        print("  [setup] ESS 방전 명령 전송")
        time.sleep(3)

        print("\n[Scenario 8] ESS 방전 중 LINE FAULT 테스트")

        # ─ 8-1: 방전 중 정상 상태 확인 ──────────────────────────────────────
        name = "S8-1 ESS 방전 상태 (operating_mode=discharge, comms_health=ok)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert len(msgs) >= MSG_COUNT, f"메시지 수 부족: {len(msgs)} < {MSG_COUNT}"
            comms  = [m["payload"]["data"]["status"]["comms_health"] for m in msgs]
            modes  = [m["payload"]["data"]["status"]["operating_mode"] for m in msgs]
            p_vals = [m["payload"]["data"]["instantaneous"]["P"] for m in msgs]
            assert all(c == "ok" for c in comms), f"comms_health 불일치: {comms}"
            assert all(m == "discharge" for m in modes), f"operating_mode 불일치: {modes}"
            log_result(name, True, f"P={p_vals[0]:.2f}kW, mode={modes[0]}")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 8-2: LINE FAULT → P=0, wire_fault ────────────────────────────────
        name = "S8-2 LINE_FAULT 후 P=0, comms_health=wire_fault"
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

        # ─ 8-3: wire_fault 중 operating_mode=discharge 유지 확인 ─────────────
        name = "S8-3 wire_fault 중 operating_mode=discharge 유지 (모드 초기화 없음)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            modes = [m["payload"]["data"]["status"]["operating_mode"] for m in msgs]
            assert all(m == "discharge" for m in modes), (
                f"wire_fault 중 모드가 바뀌어서는 안 됨: {modes}"
            )
            log_result(name, True, f"mode={modes[0]} (유지)")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 8-4: SOC 고정 확인 (방전이 멈췄으니 SOC 변화 없어야 함) ───────────
        name = "S8-4 wire_fault 중 SOC 고정"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            socs = [m["payload"]["data"]["status"]["SOC"] for m in msgs]
            assert len(set(socs)) == 1, f"SOC가 변해서는 안 됨: {socs}"
            log_result(name, True, f"SOC={socs[0]:.3f}% (고정)")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 8-5: LINE 복구 → 방전 재개 ───────────────────────────────────────
        name = "S8-5 LINE 복구 후 comms_health=ok, 방전 재개 (P>0)"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            comms  = [m["payload"]["data"]["status"]["comms_health"] for m in msgs]
            modes  = [m["payload"]["data"]["status"]["operating_mode"] for m in msgs]
            p_vals = [m["payload"]["data"]["instantaneous"]["P"] for m in msgs]
            assert all(c == "ok" for c in comms), f"comms_health: {comms}"
            assert all(m == "discharge" for m in modes), f"mode: {modes}"
            assert any(p > 0 for p in p_vals), f"방전 후 P>0 기대, got: {p_vals}"
            log_result(name, True, f"P={p_vals[0]:.2f}kW, mode={modes[0]}")
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
