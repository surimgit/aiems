"""
DieselLocalSafetyGuard 단위 테스트
rule-engine-spec.md §5.4 Diesel Edge 로컬 판단 검증

시나리오:
    1. 연료 CRITICAL → 즉시 정지 + FAULT + EMERGENCY 이벤트
    2. 냉각수 과열    → 즉시 정지 + FAULT + EMERGENCY 이벤트
    3. RPM 이상      → 즉시 정지 + FAULT + EMERGENCY 이벤트
    4. 오일 압력 이하 → 즉시 정지 + FAULT + EMERGENCY 이벤트
    5. 과부하 감지   → 출력 제한 + WARNING, 정상 복귀 시 해제
    6. 연료 LOW      → WARNING 1회, CRITICAL 이하는 별도 처리
    7. 기동 실패 3회 → FAULT 전환
    8. EMS 통신 두절 → WARNING 1회 발행
    9. FAULT 상태 명령 → BLOCKED ACK
    10. RESET 명령   → FAULT 해제 + safety_guard 초기화
"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.device.diesel_device import DieselDevice
from domain.device.models import DeviceState
from domain.device.local_safety import (
    DieselLocalSafetyGuard,
    DIESEL_FUEL_LOW,
    DIESEL_FUEL_CRITICAL,
    COOLANT_TEMP_MAX,
    RPM_NOMINAL,
    RPM_TOLERANCE,
    OIL_PRESSURE_MIN,
    OVERLOAD_RATIO,
    COMMS_TIMEOUT,
    EVT_FUEL_CRITICAL,
    EVT_COOLANT_OVERHEAT,
    EVT_RPM_ABNORMAL,
    EVT_OIL_PRESSURE_LOW,
    EVT_OVERLOAD,
    EVT_FUEL_LOW,
    EVT_COMMS_TIMEOUT,
)


# ──────────────────────────────────────────────
# 픽스처 헬퍼
# ──────────────────────────────────────────────

def make_device(max_capacity_kw: float = 1000.0) -> DieselDevice:
    """테스트용 DieselDevice 인스턴스 생성."""
    return DieselDevice(
        plant_id="PLANT-TEST",
        device_id="diesel-test",
        max_capacity_kw=max_capacity_kw,
    )


def make_running_device() -> DieselDevice:
    """RUNNING 상태의 DieselDevice 생성 (강제 전환)."""
    device = make_device()
    device.state = DeviceState.RUNNING
    device.state_start_time = datetime.now(timezone.utc)
    device.last_update_time = datetime.now(timezone.utc)
    device.data.engine.rpm = RPM_NOMINAL       # 정상 RPM
    device.data.engine.oil_pressure = OIL_PRESSURE_MIN + 1.0  # 정상 오일 압력
    device.data.engine.coolant_temp = 60.0     # 정상 온도
    device.data.fuel.level_percent = 80.0      # 충분한 연료
    device.data.fuel.remaining_liters = 1600.0
    return device


def now() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────
# 1. 연료 CRITICAL → FAULT
# ──────────────────────────────────────────────

class TestFuelCritical:
    def test_fuel_critical_stops_running_device(self):
        device = make_running_device()
        device.data.fuel.level_percent = DIESEL_FUEL_CRITICAL - 1.0
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_FUEL_CRITICAL
        assert severity == "EMERGENCY"
        assert device.state == DeviceState.FAULT
        assert device.target_p_kw == 0.0

    def test_fuel_critical_does_not_affect_stopped_device(self):
        """이미 OFF 인 경우 강제 정지 명령 없음 (이벤트는 발행)."""
        device = make_device()
        device.state = DeviceState.OFF
        device.data.fuel.level_percent = DIESEL_FUEL_CRITICAL - 1.0
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        assert event[0] == EVT_FUEL_CRITICAL
        # OFF 상태는 변경 안 함
        assert device.state == DeviceState.OFF


# ──────────────────────────────────────────────
# 2. 냉각수 과열 → FAULT
# ──────────────────────────────────────────────

class TestCoolantOverheat:
    def test_overheat_triggers_fault(self):
        device = make_running_device()
        device.data.engine.coolant_temp = COOLANT_TEMP_MAX + 5.0
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_COOLANT_OVERHEAT
        assert severity == "EMERGENCY"
        assert device.state == DeviceState.FAULT
        assert device.target_p_kw == 0.0

    def test_normal_temp_no_event(self):
        device = make_running_device()
        device.data.engine.coolant_temp = COOLANT_TEMP_MAX - 10.0

        event = device.safety_guard.check(device, now())
        assert event is None or event[0] != EVT_COOLANT_OVERHEAT


# ──────────────────────────────────────────────
# 3. RPM 이상 → FAULT
# ──────────────────────────────────────────────

class TestRpmAbnormal:
    def test_low_rpm_triggers_fault(self):
        device = make_running_device()
        rpm_min = RPM_NOMINAL * (1 - RPM_TOLERANCE)
        device.data.engine.rpm = rpm_min - 50.0
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_RPM_ABNORMAL
        assert severity == "EMERGENCY"
        assert device.state == DeviceState.FAULT

    def test_high_rpm_triggers_fault(self):
        device = make_running_device()
        rpm_max = RPM_NOMINAL * (1 + RPM_TOLERANCE)
        device.data.engine.rpm = rpm_max + 50.0
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        assert event[0] == EVT_RPM_ABNORMAL
        assert device.state == DeviceState.FAULT

    def test_rpm_check_skipped_when_not_running(self):
        """STARTING 상태에서는 RPM 이상 체크를 건너뜀."""
        device = make_device()
        device.state = DeviceState.STARTING
        device.data.engine.rpm = 0.0  # 기동 중 RPM은 0에서 시작
        device.data.fuel.level_percent = 80.0

        event = device.safety_guard.check(device, now())
        assert event is None or event[0] != EVT_RPM_ABNORMAL


# ──────────────────────────────────────────────
# 4. 오일 압력 이하 → FAULT
# ──────────────────────────────────────────────

class TestOilPressureLow:
    def test_low_oil_pressure_triggers_fault(self):
        device = make_running_device()
        device.data.engine.oil_pressure = OIL_PRESSURE_MIN - 0.5
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_OIL_PRESSURE_LOW
        assert severity == "EMERGENCY"
        assert device.state == DeviceState.FAULT
        assert device.target_p_kw == 0.0

    def test_oil_check_skipped_when_not_running(self):
        device = make_device()
        device.state = DeviceState.OFF
        device.data.engine.oil_pressure = 0.0

        event = device.safety_guard.check(device, now())
        assert event is None or event[0] != EVT_OIL_PRESSURE_LOW


# ──────────────────────────────────────────────
# 5. 과부하 → 출력 제한 + 복귀 해제
# ──────────────────────────────────────────────

class TestOverload:
    def test_overload_curtails_output(self):
        device = make_running_device()
        device.target_p_kw = device.max_capacity_kw  # 정격
        overload_p = device.max_capacity_kw * OVERLOAD_RATIO + 10.0
        device.data.instantaneous.P = overload_p
        guard = device.safety_guard

        event = guard.check(device, now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_OVERLOAD
        assert severity == "WARNING"
        assert device.target_p_kw == device.max_capacity_kw  # 정격 100%로 제한
        assert guard._overload_active is True

    def test_no_duplicate_overload_event(self):
        device = make_running_device()
        device.data.instantaneous.P = device.max_capacity_kw * OVERLOAD_RATIO + 10.0
        guard = device.safety_guard

        event1 = guard.check(device, now())
        event2 = guard.check(device, now())

        assert event1 is not None
        assert event2 is None, "중복 이벤트는 발행 안 됨"

    def test_overload_recovery_resets_flag(self):
        device = make_running_device()
        guard = device.safety_guard
        guard._overload_active = True

        # 정상 출력으로 복귀
        device.data.instantaneous.P = device.max_capacity_kw * 0.5
        guard.check(device, now())

        assert guard._overload_active is False


# ──────────────────────────────────────────────
# 6. 연료 LOW → WARNING 1회
# ──────────────────────────────────────────────

class TestFuelLow:
    def test_fuel_low_warning_emitted_once(self):
        device = make_running_device()
        # LOW 범위: DIESEL_FUEL_CRITICAL < level <= DIESEL_FUEL_LOW
        device.data.fuel.level_percent = (DIESEL_FUEL_CRITICAL + DIESEL_FUEL_LOW) / 2.0
        guard = device.safety_guard

        event1 = guard.check(device, now())
        event2 = guard.check(device, now())

        assert event1 is not None
        assert event1[0] == EVT_FUEL_LOW
        assert event1[1] == "WARNING"
        assert event2 is None, "연료 LOW 이벤트는 1회만 발행"

    def test_fuel_replenished_allows_reissue(self):
        device = make_running_device()
        device.data.fuel.level_percent = (DIESEL_FUEL_CRITICAL + DIESEL_FUEL_LOW) / 2.0
        guard = device.safety_guard

        guard.check(device, now())  # 1회 발행
        assert guard._fuel_low_reported is True

        # 연료 보충
        device.data.fuel.level_percent = 80.0
        guard.check(device, now())
        assert guard._fuel_low_reported is False


# ──────────────────────────────────────────────
# 7. 기동 실패 3회 연속 → FAULT
# ──────────────────────────────────────────────

class TestStartFailure:
    def test_three_consecutive_failures_cause_fault(self):
        device = make_running_device()  # RUNNING 상태 = 기동 명령 거부 대상
        current = now()

        for i in range(device._MAX_START_FAILURES):
            status, reason = device.execute_command(
                {"command_type": "start", "payload": {}}, current
            )
            assert status == "rejected"

        assert device.state == DeviceState.FAULT, "3회 연속 거부 시 FAULT로 전환"

    def test_successful_start_resets_failure_count(self):
        device = make_device()
        device.state = DeviceState.RUNNING  # 1회 실패 상태로 오염
        device.execute_command({"command_type": "start", "payload": {}}, now())
        assert device._start_failure_count == 1

        # RESET 후 재기동
        device.execute_command({"command_type": "mode_change", "payload": {"action": "RESET"}}, now())
        assert device._start_failure_count == 0

        status, _ = device.execute_command({"command_type": "start", "payload": {}}, now())
        assert status == "accepted"
        assert device._start_failure_count == 0  # 성공이므로 카운터 유지 (tick에서 초기화)


# ──────────────────────────────────────────────
# 8. EMS 통신 두절 → WARNING 1회
# ──────────────────────────────────────────────

class TestCommsTimeout:
    def test_comms_timeout_triggers_warning(self):
        device = make_running_device()
        guard = device.safety_guard
        guard.comms_last_seen_ts = now() - timedelta(seconds=COMMS_TIMEOUT + 5)

        event = guard.check(device, now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_COMMS_TIMEOUT
        assert severity == "WARNING"
        assert data["elapsed_seconds"] > COMMS_TIMEOUT
        # 통신 두절 시 현재 운전 상태 유지 (강제 정지 없음)
        assert device.state == DeviceState.RUNNING

    def test_no_duplicate_comms_timeout_event(self):
        device = make_running_device()
        guard = device.safety_guard
        guard.comms_last_seen_ts = now() - timedelta(seconds=COMMS_TIMEOUT + 5)

        event1 = guard.check(device, now())
        event2 = guard.check(device, now())

        assert event1 is not None
        assert event2 is None

    def test_notify_comms_alive_resets_flag(self):
        device = make_device()
        guard = device.safety_guard
        guard._comms_timeout_reported = True

        guard.notify_comms_alive()

        assert guard._comms_timeout_reported is False

    def test_no_event_before_first_comms(self):
        device = make_device()
        guard = device.safety_guard
        # comms_last_seen_ts = None (초기 상태)

        event = guard.check(device, now())
        assert event is None or event[0] != EVT_COMMS_TIMEOUT


# ──────────────────────────────────────────────
# 9. FAULT 상태 명령 → BLOCKED ACK
# ──────────────────────────────────────────────

class TestBlockedAck:
    def test_command_blocked_when_fault(self):
        device = make_device()
        device.state = DeviceState.FAULT

        status, reason = device.execute_command(
            {"command_type": "start", "payload": {}}, now()
        )

        assert status == "rejected"
        assert "LOCAL_SAFETY_BLOCKED" in reason

    def test_load_control_blocked_when_fault(self):
        device = make_device()
        device.state = DeviceState.FAULT

        status, reason = device.execute_command(
            {"command_type": "load_control", "payload": {"target_kw": 500.0}}, now()
        )

        assert status == "rejected"
        assert "LOCAL_SAFETY_BLOCKED" in reason

    def test_command_blocked_when_emergency_stop(self):
        device = make_device()
        device.state = DeviceState.EMERGENCY_STOP

        status, reason = device.execute_command(
            {"command_type": "stop", "payload": {}}, now()
        )

        assert status == "rejected"
        assert "LOCAL_SAFETY_BLOCKED" in reason


# ──────────────────────────────────────────────
# 10. RESET 명령 → FAULT 해제 + safety_guard 초기화
# ──────────────────────────────────────────────

class TestReset:
    def test_reset_clears_fault_and_guard_state(self):
        device = make_device()
        device.state = DeviceState.FAULT
        device._start_failure_count = 3
        device.safety_guard._fuel_low_reported = True
        device.safety_guard._overload_active = True
        device.safety_guard._comms_timeout_reported = True

        status, reason = device.execute_command(
            {"command_type": "mode_change", "payload": {"action": "RESET"}}, now()
        )

        assert status == "accepted"
        assert device.state == DeviceState.OFF
        assert device._start_failure_count == 0
        assert device.safety_guard._fuel_low_reported is False
        assert device.safety_guard._overload_active is False
        assert device.safety_guard._comms_timeout_reported is False
