"""
시나리오 7: 공유 선로 장애 — solar/ESS 동시 wire_fault 전파 검증

line-solar01-ess01의 affected_devices = ["solar-01", "ess-01"]
하나의 선로에 FAULT를 주입했을 때 해당 선로에 연결된 두 장치
(solar-01, ess-01)가 동시에 wire_fault 상태가 되는지 검증한다.

커버하는 케이스:
  - LINE FAULT 주입 → solar-01 wire_fault AND ess-01 wire_fault 동시 발생
  - LINE 복구 → solar-01 정상 복귀 AND ess-01 정상 복귀
"""

import time
import traceback

from utils import (
    FAULT_PROPAGATE_SEC, PLANT_ID, ESS_DEVICE_DEFAULTS,
    MqttCapture, create_edge, delete_edge, restore_topology, topo,
    assert_telemetry, log_result,
)

SOLAR_EDGE_ID = "test-shared-solar"
ESS_EDGE_ID   = "test-shared-ess"
SOLAR_DEVICE  = "solar-01"
ESS_DEVICE    = "ess-01"
SOLAR_TOPIC   = f"{PLANT_ID}/solar/{SOLAR_DEVICE}/telemetry"
ESS_TOPIC     = f"{PLANT_ID}/ess/{ESS_DEVICE}/telemetry"
LINE_ID       = "line-solar01-ess01"

MSG_COUNT = 3


def _create_both_edges():
    """두 엣지를 연속 생성. 두 번째 엣지 sleep 종료 시점에 둘 다 기동 완료."""
    create_edge("solar", SOLAR_EDGE_ID, SOLAR_DEVICE)
    create_edge("ess",   ESS_EDGE_ID,   ESS_DEVICE, extra_device_fields=ESS_DEVICE_DEFAULTS)


def run():
    cap_solar = MqttCapture()
    cap_ess   = MqttCapture()
    cap_solar.subscribe(SOLAR_TOPIC)
    cap_ess.subscribe(ESS_TOPIC)
    results = []

    try:
        _create_both_edges()
        print("\n[Scenario 7] 공유 선로 장애: Solar + ESS 동시 wire_fault 테스트")

        # ─ 7-1: solar 정상 발전 확인 ─────────────────────────────────────────
        name = "S7-1 Solar 정상 발전 (P>0, comms_health=ok)"
        try:
            cap_solar.clear()
            msgs = cap_solar.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            p = msgs[0]["payload"]["data"]["instantaneous"]["P"]
            log_result(name, True, f"P={p:.2f}kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 7-2: ESS 정상 상태 확인 ──────────────────────────────────────────
        name = "S7-2 ESS 정상 상태 (comms_health=ok)"
        try:
            cap_ess.clear()
            msgs = cap_ess.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok")
            soc = msgs[0]["payload"]["data"]["status"]["SOC"]
            log_result(name, True, f"SOC={soc:.2f}%")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 7-3/4: LINE FAULT → 두 장치 동시 wire_fault ──────────────────────
        topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": True})
        time.sleep(FAULT_PROPAGATE_SEC)

        name = "S7-3 LINE_FAULT → Solar wire_fault (P=0)"
        try:
            cap_solar.clear()
            msgs = cap_solar.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        name = "S7-4 LINE_FAULT → ESS wire_fault (P=0) — 같은 선로"
        try:
            cap_ess.clear()
            msgs = cap_ess.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="wire_fault", p_zero=True)
            log_result(name, True)
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        # ─ 7-5/6: 복구 → 두 장치 동시 정상 복귀 ────────────────────────────
        topo("PATCH", f"/api/lines/{LINE_ID}", {"fault": False})
        time.sleep(FAULT_PROPAGATE_SEC)

        name = "S7-5 LINE 복구 → Solar 정상 복귀 (P>0)"
        try:
            cap_solar.clear()
            msgs = cap_solar.collect(MSG_COUNT)
            assert_telemetry(msgs, min_count=MSG_COUNT, comms_health="ok", p_zero=False)
            p = msgs[0]["payload"]["data"]["instantaneous"]["P"]
            log_result(name, True, f"P={p:.2f}kW")
            results.append((name, True))
        except AssertionError as e:
            log_result(name, False, str(e))
            results.append((name, False))

        name = "S7-6 LINE 복구 → ESS 정상 복귀 (comms_health=ok)"
        try:
            cap_ess.clear()
            msgs = cap_ess.collect(MSG_COUNT)
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
        delete_edge(SOLAR_EDGE_ID)
        delete_edge(ESS_EDGE_ID)
        cap_solar.stop()
        cap_ess.stop()

    return results
