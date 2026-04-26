"""
시나리오 4: ESS SOC 고정(freeze) 테스트

EMS 시나리오:
  - ESS가 충전 중 → 선로 FAULT → ACK는 정상이지만 P=0, SOC 고정
  - EMS는 "충전 명령 수락됐으나 SOC가 안 오름"을 보고 선로 장애 감지
  - 선로 복구 → ESS 다시 충전, SOC 변화 재개

검증 항목:
  - wire_fault 중: power_kw=0, comms_health="wire_fault", SOC 고정
  - wire_fault 해제 후: comms_health="ok"
"""

import json
import time
import traceback

from utils import (
    FAULT_PROPAGATE_SEC, PLANT_ID,
    MqttCapture, create_edge, delete_edge, restore_topology, topo,
    assert_telemetry, log_result,
)

EDGE_ID   = "test-ess-soc"
DEVICE_ID = "ess-01"
TOPIC     = f"{PLANT_ID}/ess/{DEVICE_ID}/telemetry"
CMD_TOPIC = f"{PLANT_ID}/ess/{DEVICE_ID}/command"
LINE_ID   = "line-diesel01-ess01"   # ess-01 관련 선로

MSG_COUNT = 5


def _charge_command() -> dict:
    return {
        "command_id": "test-ess-charge-001",
        "command_type": "ess_mode",
        "expires_in_sec": 120.0,
        "payload": {"mode": "charge", "target_power_kw": 30.0},
    }


def run():
    cap = MqttCapture()
    cap.subscribe(TOPIC)
    results = []

    try:
        create_edge("ess", EDGE_ID, DEVICE_ID)

        # ── 충전 명령 전송 (ESS를 charge 모드로 전환) ─────────────────────────
        time.sleep(2)
        cap.publish(CMD_TOPIC, _charge_command())
        print("  [setup] ESS 충전 명령 전송")
        time.sleep(3)

        # ═══════════════════════════════════════════════════════════════════════
        # Scenario 4-1: 정상 충전 확인
        # ═══════════════════════════════════════════════════════════════════════
        print("\n[Scenario 4] ESS SOC 고정 테스트")
        name = "S4-1 정상 충전 상태 (P<0=charging, comms_health=ok)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            # 충전 중: P < 0 (음수 = 충전)
            p_values = [m["payload"]["data"]["instantaneous"]["P"] for m in msgs]
            comms = [m["payload"]["data"]["status"]["comms_health"] for m in msgs]
            soc_values = [m["payload"]["data"]["status"]["SOC"] for m in msgs]
            assert all(c == "ok" for c in comms), f"comms_health 불일치: {comms}"
            log_result(name, True, f"P={p_values[0]:.2f}kW, SOC={soc_values[0]:.3f}%")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ═══════════════════════════════════════════════════════════════════════
        # Scenario 4-2: wire_fault → P=0, SOC 고정
        # ═══════════════════════════════════════════════════════════════════════
        name = "S4-2 LINE_FAULT 시 P=0, comms_health=wire_fault"
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

        name = "S4-3 wire_fault 중 SOC 고정 (frozen)"
        try:
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            soc_list = [m["payload"]["data"]["status"]["SOC"] for m in msgs]
            unique = set(soc_list)
            assert len(unique) == 1, f"SOC가 변해서는 안 됨: {soc_list}"
            log_result(name, True, f"SOC={soc_list[0]:.3f}% (고정)")
            results.append((name, True))
        except (AssertionError, KeyError) as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ═══════════════════════════════════════════════════════════════════════
        # Scenario 4-4: 복구 → 정상 상태 복귀
        # ═══════════════════════════════════════════════════════════════════════
        name = "S4-4 선로 복구 후 comms_health=ok 복귀"
        try:
            topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
            time.sleep(FAULT_PROPAGATE_SEC)
            cap.clear()
            msgs = cap.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok")
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
        restore_topology()
        delete_edge(EDGE_ID)
        cap.stop()

    return results
