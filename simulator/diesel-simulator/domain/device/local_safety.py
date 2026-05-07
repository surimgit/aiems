"""
Diesel Edge 로컬 안전 판단 모듈
rule-engine-spec.md §5.4 Diesel Edge 로컬 판단 구현

판단 우선순위:
    1. 연료 CRITICAL       → 즉시 정지, FAULT (emergency)
    2. 냉각수 과열          → 즉시 정지, FAULT (emergency)
    3. RPM 이상 (±10%)    → 즉시 정지, FAULT (emergency)
    4. 오일 압력 이하       → 즉시 정지, FAULT (emergency)
    5. 과부하 감지          → 출력 정격 100%로 제한, WARNING (event)
    6. 연료 LOW 경고        → 경고 이벤트 1회 (event)
    7. EMS 통신 두절        → 자율 운전 유지, WARNING (event)
"""
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Tuple, Dict, Any

if TYPE_CHECKING:
    from domain.device.diesel_device import DieselDevice

# ──────────────────────────────────────────────
# 임계값 상수 (환경변수 우선, 없으면 기본값)
# ──────────────────────────────────────────────
DIESEL_FUEL_LOW: float      = float(os.getenv("DIESEL_FUEL_LOW",      "15.0"))  # %
DIESEL_FUEL_CRITICAL: float = float(os.getenv("DIESEL_FUEL_CRITICAL", "5.0"))   # %
COOLANT_TEMP_MAX: float     = float(os.getenv("COOLANT_TEMP_MAX",     "95.0"))  # ℃
RPM_NOMINAL: float          = float(os.getenv("RPM_NOMINAL",          "1800.0"))# rpm
RPM_TOLERANCE: float        = float(os.getenv("RPM_TOLERANCE",        "0.1"))   # ±10%
OIL_PRESSURE_MIN: float     = float(os.getenv("OIL_PRESSURE_MIN",     "2.0"))   # bar
OVERLOAD_RATIO: float       = float(os.getenv("OVERLOAD_RATIO",       "1.1"))   # 정격 110%
COMMS_TIMEOUT: float        = float(os.getenv("COMMS_TIMEOUT",        "30.0"))  # 초

# 이벤트 타입 상수
EVT_FUEL_CRITICAL    = "FUEL_CRITICAL"
EVT_COOLANT_OVERHEAT = "COOLANT_OVERHEAT"
EVT_RPM_ABNORMAL     = "RPM_ABNORMAL"
EVT_OIL_PRESSURE_LOW = "OIL_PRESSURE_LOW"
EVT_OVERLOAD         = "OVERLOAD"
EVT_FUEL_LOW         = "FUEL_LOW"
EVT_COMMS_TIMEOUT    = "COMMS_TIMEOUT"

# ──────────────────────────────────────────────
# 이벤트 결과 타입 별칭
# ──────────────────────────────────────────────
EventResult = Tuple[str, str, str, Dict[str, Any]]


class DieselLocalSafetyGuard:
    """
    DieselDevice 에 1:1로 소속되어 로컬 안전 판단을 수행.

    외부에서 호출:
        - notify_comms_alive()   : EMS 명령/메시지 수신 시
        - check(device, real_time): tick() 마다 호출
    """

    def __init__(self) -> None:
        # 통신 생존 추적
        self.comms_last_seen_ts: Optional[datetime] = None
        self._comms_timeout_reported: bool = False

        # 연료 LOW 경고 중복 방지 (CRITICAL로 escalate되면 별도 처리)
        self._fuel_low_reported: bool = False

        # 과부하 상태 추적 (중복 이벤트 방지)
        self._overload_active: bool = False

    # ──────────────────────────────────────────
    # 외부 인터페이스
    # ──────────────────────────────────────────

    def notify_comms_alive(self) -> None:
        """EMS 메시지(명령 등) 수신 시 호출하여 통신 생존 타임스탬프 갱신."""
        self.comms_last_seen_ts = datetime.now(timezone.utc)
        self._comms_timeout_reported = False  # 통신 복구 시 재발행 허용

    # ──────────────────────────────────────────
    # 핵심 판단 로직
    # ──────────────────────────────────────────

    def check(
        self,
        device: "DieselDevice",
        real_time: datetime,
    ) -> Optional[EventResult]:
        """
        로컬 안전 조건을 우선순위 순서대로 검사한다.
        위반 감지 시 device 상태를 직접 변경하고 이벤트 튜플을 반환한다.
        1회 tick 당 최대 1개 이벤트 반환 (최고 우선순위 조건 우선).

        Returns:
            (event_type, severity, message, extra_data) 또는 None
        """
        from domain.device.models import DeviceState

        # FAULT / EMERGENCY_STOP 상태이면 추가 판단 불필요
        # (단 연료/통신 체크는 OFF 상태에서도 의미 있으므로 일부 허용)
        already_faulted = device.state in [DeviceState.FAULT, DeviceState.EMERGENCY_STOP]

        if not already_faulted:
            # 1순위: 연료 CRITICAL → 즉시 정지
            event = self._check_fuel_critical(device)
            if event:
                return event

            # 2순위: 냉각수 과열 → 즉시 정지
            event = self._check_coolant_temp(device)
            if event:
                return event

            # 3순위: RPM 이상 → 즉시 정지
            event = self._check_rpm(device)
            if event:
                return event

            # 4순위: 오일 압력 이하 → 즉시 정지
            event = self._check_oil_pressure(device)
            if event:
                return event

            # 5순위: 과부하 → 출력 제한
            event = self._check_overload(device)
            if event:
                return event

        # 6순위: 연료 LOW 경고 (FAULT 상태여도 유지 중이라면 의미 있음)
        event = self._check_fuel_low(device)
        if event:
            return event

        # 7순위: EMS 통신 두절
        event = self._check_comms_timeout(device, real_time)
        if event:
            return event

        return None

    # ──────────────────────────────────────────
    # 개별 조건 검사 (private)
    # ──────────────────────────────────────────

    def _check_fuel_critical(self, device: "DieselDevice") -> Optional[EventResult]:
        """연료 잔량이 CRITICAL 임계값 이하이면 즉시 정지 + FAULT."""
        from domain.device.models import DeviceState

        fuel_pct = device.data.fuel.level_percent
        if fuel_pct <= DIESEL_FUEL_CRITICAL:
            # RUNNING 또는 STARTING 중일 때만 강제 정지
            if device.state in [DeviceState.RUNNING, DeviceState.STARTING]:
                device.state = DeviceState.FAULT
                device.target_p_kw = 0.0
            # fuel_low 플래그 초기화 (CRITICAL이 더 상위이므로)
            self._fuel_low_reported = True  # 더 이상 LOW 이벤트 발행 안 함
            return (
                EVT_FUEL_CRITICAL,
                "EMERGENCY",
                f"연료 잔량 위험 수준({fuel_pct:.1f}%). 즉시 정지.",
                {
                    "fuel_level_percent": fuel_pct,
                    "threshold_percent": DIESEL_FUEL_CRITICAL,
                    "remaining_liters": device.data.fuel.remaining_liters,
                },
            )
        return None

    def _check_coolant_temp(self, device: "DieselDevice") -> Optional[EventResult]:
        """냉각수 온도가 상한을 초과하면 즉시 정지 + FAULT."""
        from domain.device.models import DeviceState

        temp = device.data.engine.coolant_temp
        if temp > COOLANT_TEMP_MAX:
            if device.state in [DeviceState.RUNNING, DeviceState.STARTING]:
                device.state = DeviceState.FAULT
                device.target_p_kw = 0.0
            return (
                EVT_COOLANT_OVERHEAT,
                "EMERGENCY",
                f"냉각수 과열({temp:.1f}℃). 즉시 정지.",
                {
                    "coolant_temp": temp,
                    "threshold_temp": COOLANT_TEMP_MAX,
                },
            )
        return None

    def _check_rpm(self, device: "DieselDevice") -> Optional[EventResult]:
        """
        RPM이 정격(RPM_NOMINAL) 기준 ±RPM_TOLERANCE 범위를 벗어나면
        즉시 정지 + FAULT.
        RUNNING 상태일 때만 유효 (기동/정지 과도 구간 제외).
        """
        from domain.device.models import DeviceState

        if device.state != DeviceState.RUNNING:
            return None

        rpm = device.data.engine.rpm
        rpm_min = RPM_NOMINAL * (1 - RPM_TOLERANCE)
        rpm_max = RPM_NOMINAL * (1 + RPM_TOLERANCE)

        if rpm < rpm_min or rpm > rpm_max:
            device.state = DeviceState.FAULT
            device.target_p_kw = 0.0
            direction = "저하" if rpm < rpm_min else "과속"
            return (
                EVT_RPM_ABNORMAL,
                "EMERGENCY",
                f"엔진 RPM 이상({rpm:.0f}rpm, {direction}). 즉시 정지.",
                {
                    "rpm": rpm,
                    "rpm_min": rpm_min,
                    "rpm_max": rpm_max,
                },
            )
        return None

    def _check_oil_pressure(self, device: "DieselDevice") -> Optional[EventResult]:
        """오일 압력이 최솟값 이하이면 즉시 정지 + FAULT. RUNNING 상태만 유효."""
        from domain.device.models import DeviceState

        if device.state != DeviceState.RUNNING:
            return None

        pressure = device.data.engine.oil_pressure
        if pressure < OIL_PRESSURE_MIN:
            device.state = DeviceState.FAULT
            device.target_p_kw = 0.0
            return (
                EVT_OIL_PRESSURE_LOW,
                "EMERGENCY",
                f"오일 압력 이하({pressure:.2f}bar). 즉시 정지.",
                {
                    "oil_pressure": pressure,
                    "threshold_bar": OIL_PRESSURE_MIN,
                },
            )
        return None

    def _check_overload(self, device: "DieselDevice") -> Optional[EventResult]:
        """
        실제 출력이 정격 용량의 OVERLOAD_RATIO를 초과하면
        target_p를 정격 100%로 하향 제한하고 WARNING 이벤트를 1회 발행한다.
        정상 복귀 시 제한 해제.
        """
        from domain.device.models import DeviceState

        if device.state != DeviceState.RUNNING:
            # RUNNING 아닐 때 복귀 처리
            if self._overload_active:
                self._overload_active = False
            return None

        actual_p = device.data.instantaneous.P
        overload_threshold = device.max_capacity_kw * OVERLOAD_RATIO

        if actual_p > overload_threshold:
            if not self._overload_active:
                # 출력을 정격 100%로 제한
                device.target_p_kw = device.max_capacity_kw
                self._overload_active = True
                return (
                    EVT_OVERLOAD,
                    "WARNING",
                    f"과부하 감지({actual_p:.1f}kW, 정격 {device.max_capacity_kw:.0f}kW). 출력 제한 적용.",
                    {
                        "actual_p_kw": actual_p,
                        "max_capacity_kw": device.max_capacity_kw,
                        "overload_threshold_kw": overload_threshold,
                    },
                )
        else:
            # 정상 복귀
            if self._overload_active:
                self._overload_active = False
        return None

    def _check_fuel_low(self, device: "DieselDevice") -> Optional[EventResult]:
        """
        연료 잔량이 LOW 임계값 이하이면 경고 이벤트를 1회 발행한다.
        CRITICAL 임계값 이하는 별도 처리(_check_fuel_critical)에서 다룬다.
        """
        fuel_pct = device.data.fuel.level_percent

        # CRITICAL 이하는 이미 상위에서 처리됨
        if fuel_pct <= DIESEL_FUEL_CRITICAL:
            return None

        if fuel_pct <= DIESEL_FUEL_LOW:
            if not self._fuel_low_reported:
                self._fuel_low_reported = True
                return (
                    EVT_FUEL_LOW,
                    "WARNING",
                    f"연료 부족 경고({fuel_pct:.1f}%). 연료 보충 필요.",
                    {
                        "fuel_level_percent": fuel_pct,
                        "threshold_percent": DIESEL_FUEL_LOW,
                        "remaining_liters": device.data.fuel.remaining_liters,
                    },
                )
        else:
            # 연료가 보충되면 재발행 허용
            self._fuel_low_reported = False

        return None

    def _check_comms_timeout(
        self, device: "DieselDevice", real_time: datetime
    ) -> Optional[EventResult]:
        """
        EMS와의 마지막 통신으로부터 COMMS_TIMEOUT 초가 초과되면
        현재 운전 상태를 유지(자율 운전)하고 WARNING 이벤트를 1회 발행한다.
        """
        if self.comms_last_seen_ts is None:
            return None

        elapsed_seconds = (real_time - self.comms_last_seen_ts).total_seconds()

        if elapsed_seconds > COMMS_TIMEOUT:
            if not self._comms_timeout_reported:
                self._comms_timeout_reported = True
                return (
                    EVT_COMMS_TIMEOUT,
                    "WARNING",
                    f"EMS 통신 두절 {elapsed_seconds:.0f}초. 자율 운전 모드 유지.",
                    {
                        "elapsed_seconds": round(elapsed_seconds, 1),
                        "timeout_threshold": COMMS_TIMEOUT,
                        "current_state": device.state.value,
                        "current_p_kw": device.data.instantaneous.P,
                    },
                )
        return None
