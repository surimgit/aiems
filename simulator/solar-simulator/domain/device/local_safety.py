"""
Solar Edge 로컬 안전 판단 모듈
rule-engine-spec.md §5.3 Solar Edge 로컬 판단 구현

판단 우선순위:
    1. 인버터 과전압    → 즉시 출력 차단, FAULT (emergency)
    2. 계통 전압 이상   → 즉시 출력 차단, FAULT (emergency)
    3. 계통 주파수 이탈 → 출력 50% 제한, WARNING (event)
    4. 야간 지속 10분   → STANDBY 전환 (event)
    5. EMS 통신 두절   → 현재 출력 유지, WARNING (event)
"""
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Tuple, Dict, Any

if TYPE_CHECKING:
    # 순환 import 방지: 타입 힌트 전용
    from domain.device.solar_device import SolarDevice

# ──────────────────────────────────────────────
# 임계값 상수 (환경변수 우선, 없으면 기본값)
# ──────────────────────────────────────────────
GRID_FREQ_MIN: float      = float(os.getenv("GRID_FREQ_MIN",       "59.5"))  # Hz
GRID_FREQ_MAX: float      = float(os.getenv("GRID_FREQ_MAX",       "60.5"))  # Hz
GRID_VOLTAGE_MAX: float   = float(os.getenv("GRID_VOLTAGE_MAX",    "440.0")) # V (계통 전압 상한)
GRID_VOLTAGE_MIN: float   = float(os.getenv("GRID_VOLTAGE_MIN",    "340.0")) # V (계통 전압 하한)
INVERTER_OV_THRESH: float = float(os.getenv("INVERTER_OV_THRESH",  "420.0")) # V (인버터 과전압)
COMMS_TIMEOUT: float      = float(os.getenv("COMMS_TIMEOUT",       "30.0"))  # 초
NIGHT_ZERO_MINUTES: float = float(os.getenv("NIGHT_ZERO_MINUTES",  "10.0"))  # 분

# 주파수 이탈 시 출력 제한 비율 (50%)
FREQ_CURTAIL_RATIO: float = 0.5

# 이벤트 타입 상수
EVT_OVER_VOLTAGE     = "OVER_VOLTAGE"
EVT_GRID_VOLTAGE_ABN = "GRID_VOLTAGE_ABNORMAL"
EVT_FREQ_ABN         = "GRID_FREQ_ABNORMAL"
EVT_NIGHT_STANDBY    = "NIGHT_STANDBY"
EVT_COMMS_TIMEOUT    = "COMMS_TIMEOUT"

# ──────────────────────────────────────────────
# 이벤트 결과 타입 별칭
# ──────────────────────────────────────────────
EventResult = Tuple[str, str, str, Dict[str, Any]]


class SolarLocalSafetyGuard:
    """
    SolarDevice 에 1:1로 소속되어 로컬 안전 판단을 수행.
    
    외부에서 호출:
        - update_grid_state(freq_hz, voltage_v) : MQTT 텔레메트리 수신 시
        - notify_comms_alive()                  : EMS 명령/메시지 수신 시
        - check(device, sim_time, real_time)    : tick() 마다 호출
    """

    def __init__(self) -> None:
        # 계통 상태 (외부에서 갱신)
        self.grid_freq_hz: float    = 60.0
        self.grid_voltage_v: float  = 380.0

        # 통신 생존 추적
        self.comms_last_seen_ts: Optional[datetime] = None
        self._comms_timeout_reported: bool = False  # 중복 이벤트 방지

        # 야간 지속 추적
        self.zero_power_start_ts: Optional[datetime] = None
        self._night_standby_reported: bool = False  # 중복 이벤트 방지

        # 주파수 이탈 상태 추적 (중복 제한 방지)
        self._freq_curtail_active: bool = False

    # ──────────────────────────────────────────
    # 외부 인터페이스
    # ──────────────────────────────────────────

    def update_grid_state(self, freq_hz: float, voltage_v: float) -> None:
        """계통 주파수·전압 최신값 갱신 (MQTT subscriber 등 외부에서 호출)."""
        self.grid_freq_hz   = freq_hz
        self.grid_voltage_v = voltage_v

    def notify_comms_alive(self) -> None:
        """EMS 메시지(명령 등) 수신 시 호출하여 통신 생존 타임스탬프 갱신."""
        self.comms_last_seen_ts = datetime.now(timezone.utc)
        self._comms_timeout_reported = False  # 통신 복구 시 재발행 허용

    # ──────────────────────────────────────────
    # 핵심 판단 로직
    # ──────────────────────────────────────────

    def check(
        self,
        device: "SolarDevice",
        sim_time: datetime,
        real_time: datetime,
    ) -> Optional[EventResult]:
        """
        로컬 안전 조건을 순서대로 검사한다.
        위반 감지 시 device 상태를 직접 변경하고 이벤트 튜플을 반환한다.
        1회 tick 당 최대 1개 이벤트 반환 (최고 우선순위 조건 우선).

        Returns:
            (event_type, severity, message, extra_data) 또는 None
        """
        # 1순위: 인버터 과전압 → 즉시 차단 + FAULT
        event = self._check_inverter_overvoltage(device)
        if event:
            return event

        # 2순위: 계통 전압 이상 → 즉시 차단 + FAULT
        event = self._check_grid_voltage(device)
        if event:
            return event

        # 3순위: 계통 주파수 이탈 → 출력 50% 제한
        event = self._check_grid_frequency(device)
        if event:
            return event

        # 4순위: 야간 P==0 지속 10분 → STANDBY 전환
        event = self._check_night_standby(device, real_time)
        if event:
            return event

        # 5순위: EMS 통신 두절 → 현재 출력 유지 + WARNING 이벤트
        event = self._check_comms_timeout(device, real_time)
        if event:
            return event

        return None

    # ──────────────────────────────────────────
    # 개별 조건 검사 (private)
    # ──────────────────────────────────────────

    def _check_inverter_overvoltage(self, device: "SolarDevice") -> Optional[EventResult]:
        """인버터 출력 전압이 과전압 임계값을 초과하면 즉시 FAULT 처리."""
        from domain.device.models import DeviceState

        # 이미 FAULT 상태면 중복 처리 안 함
        if device.local_fault or device.emergency_stop:
            return None

        # 인버터 출력 전압 = 현재 텔레메트리 V값 사용
        inverter_v = device.data.instantaneous.V
        if inverter_v > INVERTER_OV_THRESH:
            device.local_fault = True
            device.reported_state = DeviceState.FAULT
            device.curtailment_limit_kw = 0.0  # 출력 완전 차단
            return (
                EVT_OVER_VOLTAGE,
                "EMERGENCY",
                f"인버터 과전압({inverter_v:.1f}V) 감지. 즉시 출력 차단.",
                {"voltage_v": inverter_v, "threshold_v": INVERTER_OV_THRESH},
            )
        return None

    def _check_grid_voltage(self, device: "SolarDevice") -> Optional[EventResult]:
        """계통 전압이 정상 범위를 벗어나면 즉시 FAULT 처리."""
        from domain.device.models import DeviceState

        if device.local_fault or device.emergency_stop:
            return None

        v = self.grid_voltage_v
        is_abnormal = v > GRID_VOLTAGE_MAX or v < GRID_VOLTAGE_MIN

        if is_abnormal:
            device.local_fault = True
            device.reported_state = DeviceState.FAULT
            device.curtailment_limit_kw = 0.0  # 출력 완전 차단
            direction = "과전압" if v > GRID_VOLTAGE_MAX else "저전압"
            return (
                EVT_GRID_VOLTAGE_ABN,
                "EMERGENCY",
                f"계통 전압 이상({v:.1f}V, {direction}). 즉시 출력 차단.",
                {
                    "grid_voltage_v": v,
                    "max_v": GRID_VOLTAGE_MAX,
                    "min_v": GRID_VOLTAGE_MIN,
                },
            )
        return None

    def _check_grid_frequency(self, device: "SolarDevice") -> Optional[EventResult]:
        """
        계통 주파수가 정상 범위(GRID_FREQ_MIN ~ GRID_FREQ_MAX)를 벗어나면
        출력을 현재값의 50%로 제한하고 WARNING 이벤트를 발행한다.
        주파수가 정상 복귀하면 curtailment 제한을 해제한다.
        """
        from domain.device.models import DeviceState

        # FAULT 상태는 처리 안 함
        if device.local_fault or device.emergency_stop:
            return None

        freq = self.grid_freq_hz
        is_abnormal = freq < GRID_FREQ_MIN or freq > GRID_FREQ_MAX

        if is_abnormal:
            # 이미 제한 중이면 반복 이벤트 발행 안 함
            if self._freq_curtail_active:
                return None

            # 현재 curtailment에서 50%만 적용
            current_limit = device.curtailment_limit_kw
            new_limit = current_limit * FREQ_CURTAIL_RATIO
            device.curtailment_limit_kw = new_limit
            self._freq_curtail_active = True

            direction = "저하" if freq < GRID_FREQ_MIN else "상승"
            return (
                EVT_FREQ_ABN,
                "WARNING",
                f"계통 주파수 이탈({freq:.2f}Hz, 주파수 {direction}). 출력 50% 제한 적용.",
                {
                    "grid_freq_hz": freq,
                    "min_hz": GRID_FREQ_MIN,
                    "max_hz": GRID_FREQ_MAX,
                    "curtailment_limit_kw": new_limit,
                },
            )
        else:
            # 주파수 정상 복귀 → 주파수 이유로 걸었던 제한 해제
            if self._freq_curtail_active:
                # 최대값(inf)으로 복귀하여 실질적 제한 해제
                device.curtailment_limit_kw = float("inf")
                self._freq_curtail_active = False
            return None

    def _check_night_standby(
        self, device: "SolarDevice", real_time: datetime
    ) -> Optional[EventResult]:
        """
        발전 출력 P == 0 이 NIGHT_ZERO_MINUTES 분 이상 지속되면
        STANDBY 상태로 전환하고 INFO 이벤트를 발행한다.
        """
        from domain.device.models import DeviceState, ControlMode

        # FAULT 상태는 처리 안 함
        if device.local_fault or device.emergency_stop:
            return None

        current_p = device.data.instantaneous.P

        if current_p <= 0.0:
            # 이미 보고한 경우 중복 발행 방지
            if self._night_standby_reported:
                return None

            # 출력 0 시작 시각 기록
            if self.zero_power_start_ts is None:
                self.zero_power_start_ts = real_time

            elapsed_minutes = (
                real_time - self.zero_power_start_ts
            ).total_seconds() / 60.0

            if elapsed_minutes >= NIGHT_ZERO_MINUTES:
                # AUTO 모드일 때만 강제 STANDBY 전환
                if device.mode == ControlMode.AUTO:
                    device.reported_state = DeviceState.STANDBY
                self._night_standby_reported = True
                return (
                    EVT_NIGHT_STANDBY,
                    "INFO",
                    f"야간으로 판단. P==0이 {elapsed_minutes:.1f}분 지속. STANDBY 전환.",
                    {
                        "elapsed_minutes": round(elapsed_minutes, 1),
                        "threshold_minutes": NIGHT_ZERO_MINUTES,
                    },
                )
        else:
            # 발전이 재개되면 야간 추적 초기화 (reported 여부와 무관하게 항상 리셋)
            self.zero_power_start_ts = None
            self._night_standby_reported = False

        return None


    def _check_comms_timeout(
        self, device: "SolarDevice", real_time: datetime
    ) -> Optional[EventResult]:
        """
        EMS와의 마지막 통신으로부터 COMMS_TIMEOUT 초가 초과되면
        현재 출력을 유지하고 WARNING 이벤트를 1회 발행한다.
        """
        # 아직 한 번도 통신이 없었으면 판단 보류
        if self.comms_last_seen_ts is None:
            return None

        elapsed_seconds = (real_time - self.comms_last_seen_ts).total_seconds()

        if elapsed_seconds > COMMS_TIMEOUT:
            if not self._comms_timeout_reported:
                self._comms_timeout_reported = True
                return (
                    EVT_COMMS_TIMEOUT,
                    "WARNING",
                    f"EMS 통신 두절 {elapsed_seconds:.0f}초. 현재 출력 유지.",
                    {
                        "elapsed_seconds": round(elapsed_seconds, 1),
                        "timeout_threshold": COMMS_TIMEOUT,
                        "current_p_kw": device.data.instantaneous.P,
                    },
                )
        return None
