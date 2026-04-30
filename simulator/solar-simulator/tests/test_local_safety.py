"""
SolarLocalSafetyGuard 단위 테스트
rule-engine-spec.md §5.3 Solar Edge 로컬 판단 검증

시나리오:
    1. 인버터 과전압 → FAULT 전이 + EMERGENCY 이벤트 확인
    2. 계통 전압 이상 (과전압/저전압) → FAULT 전이 확인
    3. 계통 주파수 이탈 → WARNING 이벤트 + curtailment 50% 적용 확인
    4. 야간 10분 지속 → STANDBY 전환 + INFO 이벤트 확인
    5. EMS 통신 두절 → WARNING 이벤트 1회 발행 확인
    6. FAULT 상태 명령 → BLOCKED ACK (rejected) 확인
    7. RESET 명령 → FAULT 해제 + safety_guard 상태 초기화 확인
"""
import sys
import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.device.solar_device import SolarDevice
from domain.device.models import DeviceState
from domain.device.local_safety import (
    SolarLocalSafetyGuard,
    INVERTER_OV_THRESH,
    GRID_VOLTAGE_MAX,
    GRID_VOLTAGE_MIN,
    GRID_FREQ_MIN,
    GRID_FREQ_MAX,
    COMMS_TIMEOUT,
    NIGHT_ZERO_MINUTES,
    EVT_OVER_VOLTAGE,
    EVT_GRID_VOLTAGE_ABN,
    EVT_FREQ_ABN,
    EVT_NIGHT_STANDBY,
    EVT_COMMS_TIMEOUT,
)


# ──────────────────────────────────────────────
# 테스트 픽스처 헬퍼
# ──────────────────────────────────────────────

def make_device() -> SolarDevice:
    """테스트용 SolarDevice 인스턴스 생성 (interpolator는 Mock으로 대체)."""
    mock_interpolator = MagicMock()
    mock_interpolator.get_interpolated_value.return_value = 100_000.0  # 100kW (Watt)
    mock_interpolator.get_first_time.return_value = datetime.now(timezone.utc)
    return SolarDevice(
        plant_id="PLANT-TEST",
        device_id="solar-test",
        interpolator=mock_interpolator,
    )


def now() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────
# 1. 인버터 과전압 → FAULT + EMERGENCY
# ──────────────────────────────────────────────

class TestInverterOvervoltage:
    def test_overvoltage_triggers_fault_and_emergency_event(self):
        device = make_device()
        guard = device.safety_guard

        # 인버터 출력 전압을 임계값 초과로 설정
        device.data.instantaneous.V = INVERTER_OV_THRESH + 10.0

        event = guard.check(device, now(), now())

        assert event is not None, "과전압 시 이벤트가 반환되어야 함"
        evt_type, severity, _, data = event
        assert evt_type == EVT_OVER_VOLTAGE
        assert severity == "EMERGENCY"
        assert device.local_fault is True, "local_fault가 True로 전환되어야 함"
        assert device.reported_state == DeviceState.FAULT
        assert device.curtailment_limit_kw == 0.0, "출력이 완전 차단되어야 함"

    def test_normal_voltage_no_event(self):
        device = make_device()
        device.data.instantaneous.V = 380.0  # 정상 전압

        event = device.safety_guard.check(device, now(), now())
        assert event is None or event[0] != EVT_OVER_VOLTAGE


# ──────────────────────────────────────────────
# 2. 계통 전압 이상 → FAULT
# ──────────────────────────────────────────────

class TestGridVoltageAbnormal:
    def test_grid_overvoltage_triggers_fault(self):
        device = make_device()
        guard = device.safety_guard
        guard.update_grid_state(freq_hz=60.0, voltage_v=GRID_VOLTAGE_MAX + 5.0)

        event = guard.check(device, now(), now())

        assert event is not None
        evt_type, severity, _, _ = event
        assert evt_type == EVT_GRID_VOLTAGE_ABN
        assert severity == "EMERGENCY"
        assert device.local_fault is True
        assert device.reported_state == DeviceState.FAULT

    def test_grid_undervoltage_triggers_fault(self):
        device = make_device()
        guard = device.safety_guard
        guard.update_grid_state(freq_hz=60.0, voltage_v=GRID_VOLTAGE_MIN - 5.0)

        event = guard.check(device, now(), now())

        assert event is not None
        evt_type, severity, _, _ = event
        assert evt_type == EVT_GRID_VOLTAGE_ABN
        assert severity == "EMERGENCY"
        assert device.local_fault is True

    def test_normal_grid_voltage_no_event(self):
        device = make_device()
        guard = device.safety_guard
        guard.update_grid_state(freq_hz=60.0, voltage_v=380.0)

        event = guard.check(device, now(), now())
        assert event is None or event[0] != EVT_GRID_VOLTAGE_ABN


# ──────────────────────────────────────────────
# 3. 계통 주파수 이탈 → WARNING + 출력 50% 제한
# ──────────────────────────────────────────────

class TestGridFrequencyAbnormal:
    def test_low_frequency_curtails_50_percent(self):
        device = make_device()
        guard = device.safety_guard
        original_limit = device.curtailment_limit_kw  # float('inf')
        guard.update_grid_state(freq_hz=GRID_FREQ_MIN - 1.0, voltage_v=380.0)

        event = guard.check(device, now(), now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_FREQ_ABN
        assert severity == "WARNING"
        # curtailment는 original_limit * 0.5 = inf * 0.5 = inf(특수 케이스),
        # 실제로는 현재 curtailment_limit이 inf이므로 결과도 inf이지만 상태 플래그 확인
        assert guard._freq_curtail_active is True

    def test_high_frequency_curtails_50_percent(self):
        device = make_device()
        device.curtailment_limit_kw = 200.0  # 기존 제한 설정 후 테스트
        guard = device.safety_guard
        guard.update_grid_state(freq_hz=GRID_FREQ_MAX + 1.0, voltage_v=380.0)

        event = guard.check(device, now(), now())

        assert event is not None
        _, _, _, data = event
        # 200.0 * 0.5 = 100.0
        assert data["curtailment_limit_kw"] == 100.0
        assert device.curtailment_limit_kw == 100.0

    def test_frequency_recovery_resets_curtailment(self):
        device = make_device()
        device.curtailment_limit_kw = 200.0
        guard = device.safety_guard

        # 주파수 이탈 → 제한 적용
        guard.update_grid_state(freq_hz=GRID_FREQ_MIN - 1.0, voltage_v=380.0)
        guard.check(device, now(), now())
        assert guard._freq_curtail_active is True

        # 주파수 정상 복귀
        guard.update_grid_state(freq_hz=60.0, voltage_v=380.0)
        event = guard.check(device, now(), now())

        assert guard._freq_curtail_active is False
        assert device.curtailment_limit_kw == float("inf"), "복귀 시 제한 해제되어야 함"

    def test_no_duplicate_freq_event(self):
        """주파수 이탈이 지속되어도 이벤트는 최초 1회만 발행."""
        device = make_device()
        guard = device.safety_guard
        guard.update_grid_state(freq_hz=GRID_FREQ_MIN - 1.0, voltage_v=380.0)

        event1 = guard.check(device, now(), now())
        event2 = guard.check(device, now(), now())

        assert event1 is not None
        assert event2 is None, "중복 이벤트는 발행되지 않아야 함"


# ──────────────────────────────────────────────
# 4. 야간 지속 → STANDBY
# ──────────────────────────────────────────────

class TestNightStandby:
    def test_night_standby_after_threshold(self):
        device = make_device()
        guard = device.safety_guard

        # P == 0 설정
        device.data.instantaneous.P = 0.0

        # 기준 시작 시각: NIGHT_ZERO_MINUTES + 1분 전
        start_time = now() - timedelta(minutes=NIGHT_ZERO_MINUTES + 1)
        guard.zero_power_start_ts = start_time

        event = guard.check(device, now(), now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_NIGHT_STANDBY
        assert severity == "INFO"
        assert device.reported_state == DeviceState.STANDBY

    def test_no_night_standby_before_threshold(self):
        device = make_device()
        guard = device.safety_guard
        device.data.instantaneous.P = 0.0
        # 아직 임계 시간 미달
        guard.zero_power_start_ts = now() - timedelta(minutes=NIGHT_ZERO_MINUTES - 1)

        event = guard.check(device, now(), now())
        assert event is None or event[0] != EVT_NIGHT_STANDBY

    def test_power_resume_resets_night_timer(self):
        device = make_device()
        guard = device.safety_guard
        guard.zero_power_start_ts = now() - timedelta(minutes=NIGHT_ZERO_MINUTES + 5)
        guard._night_standby_reported = True

        # 발전 재개
        device.data.instantaneous.P = 50.0
        guard.check(device, now(), now())

        assert guard.zero_power_start_ts is None
        assert guard._night_standby_reported is False


# ──────────────────────────────────────────────
# 5. EMS 통신 두절 → WARNING 이벤트 1회
# ──────────────────────────────────────────────

class TestCommsTimeout:
    def test_comms_timeout_triggers_warning(self):
        device = make_device()
        guard = device.safety_guard

        # 통신 두절 상황: 마지막 수신이 COMMS_TIMEOUT 초 이전
        guard.comms_last_seen_ts = now() - timedelta(seconds=COMMS_TIMEOUT + 5)

        event = guard.check(device, now(), now())

        assert event is not None
        evt_type, severity, _, data = event
        assert evt_type == EVT_COMMS_TIMEOUT
        assert severity == "WARNING"
        assert data["elapsed_seconds"] > COMMS_TIMEOUT

    def test_no_duplicate_comms_timeout_event(self):
        """통신 두절이 지속되어도 이벤트는 1회만 발행."""
        device = make_device()
        guard = device.safety_guard
        guard.comms_last_seen_ts = now() - timedelta(seconds=COMMS_TIMEOUT + 5)

        event1 = guard.check(device, now(), now())
        event2 = guard.check(device, now(), now())

        assert event1 is not None
        assert event2 is None

    def test_comms_alive_resets_flag(self):
        device = make_device()
        guard = device.safety_guard
        guard.comms_last_seen_ts = now() - timedelta(seconds=COMMS_TIMEOUT + 5)
        guard._comms_timeout_reported = True

        guard.notify_comms_alive()

        assert guard._comms_timeout_reported is False

    def test_no_event_before_first_comms(self):
        """아직 한 번도 통신이 없으면 COMMS_TIMEOUT 이벤트를 발행하지 않는다."""
        device = make_device()
        guard = device.safety_guard
        # comms_last_seen_ts = None (초기 상태)

        event = guard.check(device, now(), now())
        assert event is None or event[0] != EVT_COMMS_TIMEOUT


# ──────────────────────────────────────────────
# 6. FAULT 상태 명령 → BLOCKED ACK
# ──────────────────────────────────────────────

class TestBlockedAck:
    def test_command_blocked_when_fault(self):
        device = make_device()
        device.local_fault = True
        device.reported_state = DeviceState.FAULT

        status, reason = device.execute_command(
            {"command_type": "curtailment", "payload": {"limit_kw": 50.0}},
            now(),
        )

        assert status == "rejected"
        assert "LOCAL_SAFETY_BLOCKED" in reason

    def test_command_blocked_when_emergency_stop(self):
        device = make_device()
        device.emergency_stop = True
        device.reported_state = DeviceState.FAULT

        status, reason = device.execute_command(
            {"command_type": "curtailment", "payload": {"limit_kw": 50.0}},
            now(),
        )

        assert status == "rejected"
        assert "LOCAL_SAFETY_BLOCKED" in reason


# ──────────────────────────────────────────────
# 7. RESET 명령 → FAULT 해제 + safety_guard 초기화
# ──────────────────────────────────────────────

class TestReset:
    def test_reset_clears_fault_and_guard_state(self):
        device = make_device()
        # FAULT 상태 + guard 내부 플래그 오염 설정
        device.local_fault = True
        device.reported_state = DeviceState.FAULT
        device.safety_guard._freq_curtail_active = True
        device.safety_guard._comms_timeout_reported = True
        device.safety_guard._night_standby_reported = True

        status, reason = device.execute_command(
            {"command_type": "mode_change", "payload": {"action": "RESET"}},
            now(),
        )

        assert status == "accepted"
        assert device.local_fault is False
        assert device.reported_state == DeviceState.STANDBY
        assert device.safety_guard._freq_curtail_active is False
        assert device.safety_guard._comms_timeout_reported is False
        assert device.safety_guard._night_standby_reported is False
