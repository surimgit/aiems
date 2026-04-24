from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .calculations import (
    apply_soc_delta,
    calculate_energy_delta_kwh,
    calculate_energy_increment,
    calculate_signed_power,
    calculate_soc_delta,
    clamp_soc,
)
from .policies import ensure_charge_allowed, ensure_discharge_allowed, evaluate_safety_transition
from .profile_engine import EssProfile, ProfileContext
from .state_machine import EssState, OperatingMode, resolve_safety_state, sync_state_with_mode, validate_mode_transition
from .validators import validate_percent_range, validate_positive, validate_threshold_pair


@dataclass
class DeviceSpec:
    plant_id: str
    device_id: str
    resource_type: str
    publish_interval_sec: float
    power_limit_kw: float
    capacity_kwh: float


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
    interlock_active: bool = False
    comms_healthy: bool = True
    last_updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ems_controlled: bool = False
    ems_control_expires_at: datetime | None = None


class EssSimulator:
    def __init__(
        self,
        device_spec: DeviceSpec,
        safety_spec: SafetySpec,
        initial_soc: float,
        temperature_c: float = 25.0,
        profile: EssProfile | None = None,
    ) -> None:
        self.device_spec = device_spec
        self.safety_spec = safety_spec
        self.profile = profile
        self.status = EssStatus(soc=initial_soc, temperature_c=temperature_c)

    def set_mode(self, mode: OperatingMode, target_power_kw: float | None = None, expires_in_sec: float = 60.0) -> None:
        target_state = validate_mode_transition(
            current_state=self.status.state,
            current_mode=self.status.operating_mode,
            requested_mode=mode,
            local_fault=self.status.local_fault,
            emergency_stop=self.status.emergency_stop,
        )
        self._ensure_mode_allowed(mode)
        self._enter_in_progress_state()
        self._apply_mode_state(target_state, mode, target_power_kw)
        # EMS가 제어권을 가져감 — 만료 전까지 프로파일이 모드를 덮어쓰지 않음
        self.status.ems_controlled = True
        self.status.ems_control_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_sec)

    def update_device_spec(
        self,
        *,
        power_limit_kw: float | None = None,
        publish_interval_sec: float | None = None,
        capacity_kwh: float | None = None,
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

        if capacity_kwh is not None:
            validate_positive(capacity_kwh, "capacity_kwh")
            self.device_spec.capacity_kwh = capacity_kwh
            applied["capacity_kwh"] = capacity_kwh

        self.status.last_updated_at = datetime.now(timezone.utc)
        return applied

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

    def tick(self) -> dict[str, object]:
        validate_positive(self.device_spec.publish_interval_sec, "publish_interval_sec")
        validate_positive(self.device_spec.power_limit_kw, "power_limit_kw")
        validate_positive(self.device_spec.capacity_kwh, "capacity_kwh")

        self._apply_profile()
        self._advance_soc()
        self._accumulate_energy()
        self._apply_safety_rules()
        self.status.last_updated_at = datetime.now(timezone.utc)
        return self.snapshot()

    def snapshot(self) -> dict[str, object]:
        return {
            "plant_id": self.device_spec.plant_id,
            "device_id": self.device_spec.device_id,
            "resource_type": self.device_spec.resource_type,
            "publish_interval_sec": self.device_spec.publish_interval_sec,
            "power_limit_kw": self.device_spec.power_limit_kw,
            "capacity_kwh": self.device_spec.capacity_kwh,
            "soc": round(self.status.soc, 3),
            "power_kw": round(self.status.power_kw, 3),
            "target_power_kw": round(self.status.target_power_kw, 3),
            "operating_mode": self.status.operating_mode,
            "state": self.status.state,
            "temperature_c": round(self.status.temperature_c, 3),
            "accumulated_energy_kwh": round(self.status.accumulated_energy_kwh, 3),
            "local_fault": self.status.local_fault,
            "emergency_stop": self.status.emergency_stop,
            "interlock_active": self.status.interlock_active,
            "comms_healthy": self.status.comms_healthy,
            "low_soc_threshold": self.safety_spec.low_soc_threshold,
            "high_soc_threshold": self.safety_spec.high_soc_threshold,
            "min_safe_soc_threshold": self.safety_spec.min_safe_soc_threshold,
            "max_safe_soc_threshold": self.safety_spec.max_safe_soc_threshold,
            "max_temperature_c": self.safety_spec.max_temperature_c,
            "timestamp": self.status.last_updated_at.isoformat(),
        }

    def set_interlock_active(self, active: bool) -> None:
        self.status.interlock_active = active
        self.status.last_updated_at = datetime.now(timezone.utc)

    def set_comms_health(self, healthy: bool) -> None:
        self.status.comms_healthy = healthy
        self.status.last_updated_at = datetime.now(timezone.utc)

    def set_emergency_stop(self, active: bool) -> None:
        self.status.emergency_stop = active
        self.status.last_updated_at = datetime.now(timezone.utc)
        self._apply_safety_rules()

    def _apply_profile(self) -> None:
        if self.profile is None:
            return

        # EMS 제어권 만료 여부 확인
        if self.status.ems_controlled:
            if (
                self.status.ems_control_expires_at is not None
                and datetime.now(timezone.utc) >= self.status.ems_control_expires_at
            ):
                self.status.ems_controlled = False
                self.status.ems_control_expires_at = None
            else:
                # EMS 제어 중: 온도 노이즈만 반영, 전력/모드는 건드리지 않음
                generated = self.profile.generate(
                    ProfileContext(
                        sim_time=self.status.last_updated_at,
                        publish_interval_sec=self.device_spec.publish_interval_sec,
                        soc=self.status.soc,
                        power_limit_kw=self.device_spec.power_limit_kw,
                        capacity_kwh=self.device_spec.capacity_kwh,
                        temperature_c=self.status.temperature_c,
                        device_id=self.device_spec.device_id,
                    )
                )
                self.status.temperature_c = generated.temperature_c
                return

        # 자율 운전: 프로파일이 전력/모드 전체를 결정
        generated = self.profile.generate(
            ProfileContext(
                sim_time=self.status.last_updated_at,
                publish_interval_sec=self.device_spec.publish_interval_sec,
                soc=self.status.soc,
                power_limit_kw=self.device_spec.power_limit_kw,
                capacity_kwh=self.device_spec.capacity_kwh,
                temperature_c=self.status.temperature_c,
                device_id=self.device_spec.device_id,
            )
        )
        self.status.power_kw = generated.power_kw
        self.status.target_power_kw = abs(generated.power_kw)
        self.status.temperature_c = generated.temperature_c
        if generated.power_kw > 0:
            self.status.operating_mode = "discharge"
        elif generated.power_kw < 0:
            self.status.operating_mode = "charge"
        else:
            self.status.operating_mode = "standby"

    def _ensure_mode_allowed(self, mode: OperatingMode) -> None:
        if mode == "charge":
            ensure_charge_allowed(
                soc=self.status.soc,
                temperature_c=self.status.temperature_c,
                high_soc_threshold=self.safety_spec.high_soc_threshold,
                max_safe_soc_threshold=self.safety_spec.max_safe_soc_threshold,
                max_temperature_c=self.safety_spec.max_temperature_c,
            )
            return

        if mode == "discharge":
            ensure_discharge_allowed(
                soc=self.status.soc,
                temperature_c=self.status.temperature_c,
                low_soc_threshold=self.safety_spec.low_soc_threshold,
                min_safe_soc_threshold=self.safety_spec.min_safe_soc_threshold,
                max_temperature_c=self.safety_spec.max_temperature_c,
            )

    def _enter_in_progress_state(self) -> None:
        self.status.state = "IN_PROGRESS"

    def _apply_mode_state(
        self,
        target_state: EssState,
        mode: OperatingMode,
        target_power_kw: float | None,
    ) -> None:
        requested_power = target_power_kw if target_power_kw is not None else 0.0
        validate_positive(self.device_spec.power_limit_kw, "power_limit_kw")
        clamped_power = max(0.0, min(requested_power, self.device_spec.power_limit_kw))
        self.status.operating_mode = mode
        self.status.target_power_kw = clamped_power
        self.status.power_kw = calculate_signed_power(mode, clamped_power)
        self.status.state = target_state
        self.status.last_updated_at = datetime.now(timezone.utc)

    def _advance_soc(self) -> None:
        if self.status.operating_mode == "standby":
            return

        energy_delta_kwh = calculate_energy_delta_kwh(self.status.power_kw, self.device_spec.publish_interval_sec)
        soc_delta = calculate_soc_delta(energy_delta_kwh, self.device_spec.capacity_kwh, self.status.operating_mode)
        next_soc = apply_soc_delta(self.status.soc, soc_delta, self.status.operating_mode)
        self.status.soc = clamp_soc(next_soc)

    def _accumulate_energy(self) -> None:
        self.status.accumulated_energy_kwh += calculate_energy_increment(
            self.status.power_kw,
            self.device_spec.publish_interval_sec,
        )

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

        forced_state = resolve_safety_state(force_safe_stop, local_fault)
        if forced_state is not None:
            self.status.local_fault = local_fault
            self.status.state = forced_state
            self.status.operating_mode = "standby"
            self.status.target_power_kw = 0.0
            self.status.power_kw = 0.0
            return

        self.status.state = sync_state_with_mode(
            current_state=self.status.state,
            operating_mode=self.status.operating_mode,
            local_fault=self.status.local_fault,
            emergency_stop=self.status.emergency_stop,
        )
