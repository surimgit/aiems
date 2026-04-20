from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

from .calculations import calculate_energy_increment, calculate_signed_power, calculate_soc_delta
from .policies import ensure_charge_allowed, ensure_discharge_allowed, evaluate_safety_transition
from .validators import validate_percent_range, validate_positive, validate_threshold_pair


OperatingMode = Literal["charge", "discharge", "standby"]
EssState = Literal[
    "IDLE",
    "STANDBY",
    "CHARGING",
    "DISCHARGING",
    "FAULT",
    "SAFE_STOP",
    "EMERGENCY_STOP",
]


@dataclass
class DeviceSpec:
    plant_id: str
    device_id: str
    resource_type: str
    publish_interval_sec: float
    power_limit_kw: float


@dataclass
class SafetySpec:
    low_soc_threshold: float
    high_soc_threshold: float
    min_safe_soc_threshold: float
    max_safe_soc_threshold: float
    max_temperature_c: float


@dataclass
class EssStatus:
    soc: float
    power_kw: float = 0.0
    target_power_kw: float = 0.0
    operating_mode: OperatingMode = "standby"
    state: EssState = "STANDBY"
    temperature_c: float = 25.0
    accumulated_energy_kwh: float = 0.0
    local_fault: bool = False
    emergency_stop: bool = False
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class EssSimulator:
    # ESS 시뮬레이터의 기본 스펙, 안전 기준, 현재 상태를 초기화한다.
    def __init__(
        self,
        device_spec: DeviceSpec,
        safety_spec: SafetySpec,
        initial_soc: float,
        temperature_c: float = 25.0,
    ) -> None:
        self.device_spec = device_spec
        self.safety_spec = safety_spec
        self.status = EssStatus(
            soc=initial_soc,
            temperature_c=temperature_c,
        )

    # 외부 명령에 따라 충전/방전/대기 모드를 변경한다.
    def set_mode(self, mode: OperatingMode, target_power_kw: float | None = None) -> None:
        if self.status.emergency_stop:
            raise ValueError("Emergency stop active")
        if self.status.local_fault:
            raise ValueError("Local fault active")

        if mode == "charge":
            ensure_charge_allowed(
                soc=self.status.soc,
                temperature_c=self.status.temperature_c,
                high_soc_threshold=self.safety_spec.high_soc_threshold,
                max_safe_soc_threshold=self.safety_spec.max_safe_soc_threshold,
                max_temperature_c=self.safety_spec.max_temperature_c,
            )
            self.status.state = "CHARGING"
        elif mode == "discharge":
            ensure_discharge_allowed(
                soc=self.status.soc,
                temperature_c=self.status.temperature_c,
                low_soc_threshold=self.safety_spec.low_soc_threshold,
                min_safe_soc_threshold=self.safety_spec.min_safe_soc_threshold,
                max_temperature_c=self.safety_spec.max_temperature_c,
            )
            self.status.state = "DISCHARGING"
        else:
            self.status.state = "STANDBY"

        self.status.operating_mode = mode
        requested_power = target_power_kw if target_power_kw is not None else 0.0
        validate_positive(self.device_spec.power_limit_kw, "power_limit_kw")
        self.status.target_power_kw = max(0.0, min(requested_power, self.device_spec.power_limit_kw))
        self.status.power_kw = calculate_signed_power(self.status.operating_mode, self.status.target_power_kw)
        self.status.last_updated_at = datetime.now(timezone.utc)

    # 실행 중 장치 스펙을 변경한다.
    def update_device_spec(
        self,
        *,
        power_limit_kw: float | None = None,
        publish_interval_sec: float | None = None,
    ) -> dict[str, float]:
        applied: dict[str, float] = {}
        if power_limit_kw is not None:
            validate_positive(power_limit_kw, "power_limit_kw")
            self.device_spec.power_limit_kw = power_limit_kw
            if self.status.target_power_kw > power_limit_kw:
                self.status.target_power_kw = power_limit_kw
                self.status.power_kw = calculate_signed_power(self.status.operating_mode, power_limit_kw)
            applied["power_limit_kw"] = power_limit_kw

        if publish_interval_sec is not None:
            validate_positive(publish_interval_sec, "publish_interval_sec")
            self.device_spec.publish_interval_sec = publish_interval_sec
            applied["publish_interval_sec"] = publish_interval_sec

        self.status.last_updated_at = datetime.now(timezone.utc)
        return applied

    # 실행 중 안전 기준값을 변경한다.
    def update_safety_spec(
        self,
        *,
        low_soc_threshold: float | None = None,
        high_soc_threshold: float | None = None,
        min_safe_soc_threshold: float | None = None,
        max_safe_soc_threshold: float | None = None,
        max_temperature_c: float | None = None,
    ) -> dict[str, float]:
        next_low = self.safety_spec.low_soc_threshold if low_soc_threshold is None else low_soc_threshold
        next_high = self.safety_spec.high_soc_threshold if high_soc_threshold is None else high_soc_threshold
        next_min_safe = self.safety_spec.min_safe_soc_threshold if min_safe_soc_threshold is None else min_safe_soc_threshold
        next_max_safe = self.safety_spec.max_safe_soc_threshold if max_safe_soc_threshold is None else max_safe_soc_threshold

        validate_threshold_pair(next_low, next_high, "low_soc_threshold", "high_soc_threshold")
        validate_threshold_pair(next_min_safe, next_max_safe, "min_safe_soc_threshold", "max_safe_soc_threshold")

        applied: dict[str, float] = {}
        if low_soc_threshold is not None:
            self.safety_spec.low_soc_threshold = low_soc_threshold
            applied["low_soc_threshold"] = low_soc_threshold
        if high_soc_threshold is not None:
            self.safety_spec.high_soc_threshold = high_soc_threshold
            applied["high_soc_threshold"] = high_soc_threshold
        if min_safe_soc_threshold is not None:
            self.safety_spec.min_safe_soc_threshold = min_safe_soc_threshold
            applied["min_safe_soc_threshold"] = min_safe_soc_threshold
        if max_safe_soc_threshold is not None:
            self.safety_spec.max_safe_soc_threshold = max_safe_soc_threshold
            applied["max_safe_soc_threshold"] = max_safe_soc_threshold
        if max_temperature_c is not None:
            validate_positive(max_temperature_c, "max_temperature_c")
            self.safety_spec.max_temperature_c = max_temperature_c
            applied["max_temperature_c"] = max_temperature_c

        self._apply_safety_rules()
        self.status.last_updated_at = datetime.now(timezone.utc)
        return applied

    # 한 tick 동안 ESS 상태를 진행시키고 최신 스냅샷을 반환한다.
    def tick(self) -> dict[str, object]:
        validate_positive(self.device_spec.publish_interval_sec, "publish_interval_sec")
        validate_positive(self.device_spec.power_limit_kw, "power_limit_kw")

        if self.status.operating_mode == "charge":
            soc_delta = calculate_soc_delta(
                self.status.power_kw,
                self.device_spec.publish_interval_sec,
                self.device_spec.power_limit_kw,
            )
            self.status.soc = min(100.0, self.status.soc + soc_delta)
        elif self.status.operating_mode == "discharge":
            soc_delta = calculate_soc_delta(
                self.status.power_kw,
                self.device_spec.publish_interval_sec,
                self.device_spec.power_limit_kw,
            )
            self.status.soc = max(0.0, self.status.soc - soc_delta)

        self.status.accumulated_energy_kwh += calculate_energy_increment(
            self.status.power_kw,
            self.device_spec.publish_interval_sec,
        )
        self._apply_safety_rules()
        self.status.last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    # 현재 상태를 외부에 전달하기 쉬운 딕셔너리 형태로 만든다.
    def snapshot(self) -> dict[str, object]:
        return {
            "plant_id": self.device_spec.plant_id,
            "device_id": self.device_spec.device_id,
            "resource_type": self.device_spec.resource_type,
            "publish_interval_sec": self.device_spec.publish_interval_sec,
            "power_limit_kw": self.device_spec.power_limit_kw,
            "soc": round(self.status.soc, 3),
            "power_kw": round(self.status.power_kw, 3),
            "target_power_kw": round(self.status.target_power_kw, 3),
            "operating_mode": self.status.operating_mode,
            "state": self.status.state,
            "temperature_c": round(self.status.temperature_c, 3),
            "accumulated_energy_kwh": round(self.status.accumulated_energy_kwh, 3),
            "local_fault": self.status.local_fault,
            "emergency_stop": self.status.emergency_stop,
            "low_soc_threshold": self.safety_spec.low_soc_threshold,
            "high_soc_threshold": self.safety_spec.high_soc_threshold,
            "min_safe_soc_threshold": self.safety_spec.min_safe_soc_threshold,
            "max_safe_soc_threshold": self.safety_spec.max_safe_soc_threshold,
            "max_temperature_c": self.safety_spec.max_temperature_c,
            "timestamp": self.status.last_updated_at.isoformat(),
        }

    # 현재 상태가 안전 기준을 넘었는지 확인하고 필요하면 강제로 정지 상태로 바꾼다.
    def _apply_safety_rules(self) -> None:
        validate_percent_range(self.status.soc, "soc")
        force_safe_stop, local_fault = evaluate_safety_transition(
            soc=self.status.soc,
            temperature_c=self.status.temperature_c,
            operating_mode=self.status.operating_mode,
            min_safe_soc_threshold=self.safety_spec.min_safe_soc_threshold,
            max_safe_soc_threshold=self.safety_spec.max_safe_soc_threshold,
            max_temperature_c=self.safety_spec.max_temperature_c,
        )

        if force_safe_stop:
            self.status.local_fault = local_fault
            self.status.state = "SAFE_STOP"
            self.status.operating_mode = "standby"
            self.status.target_power_kw = 0.0
            self.status.power_kw = 0.0
            return

        if not self.status.local_fault and not self.status.emergency_stop and self.status.operating_mode == "standby":
            self.status.state = "STANDBY"
