from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from core.load import LoadDevice, LoadFleet, LoadMeasurement


@dataclass(slots=True)
class ScenarioProfile:
    name: str
    noise_ratio: float
    peak_hours: tuple[int, ...]
    peak_multiplier: float
    off_peak_multiplier: float = 1.0
    weekend_multiplier: float = 1.0
    minimum_load_ratio: float = 0.0

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("scenario profile name is required")
        if self.noise_ratio < 0:
            raise ValueError("noise_ratio must be greater than or equal to 0")
        if self.peak_multiplier < 1:
            raise ValueError("peak_multiplier must be greater than or equal to 1")
        if self.off_peak_multiplier <= 0:
            raise ValueError("off_peak_multiplier must be greater than 0")
        if self.weekend_multiplier <= 0:
            raise ValueError("weekend_multiplier must be greater than 0")
        if not 0.0 <= self.minimum_load_ratio <= 1.0:
            raise ValueError("minimum_load_ratio must be between 0.0 and 1.0")
        for hour in self.peak_hours:
            if not 0 <= hour <= 23:
                raise ValueError("peak_hours must contain values between 0 and 23")


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        raise ValueError("yaml root must be a mapping")
    return loaded


def load_scenario_profiles(path: str | Path) -> dict[str, ScenarioProfile]:
    raw = _load_yaml(path)
    profiles = raw.get("profiles", {})
    if not isinstance(profiles, dict):
        raise ValueError("profiles must be a mapping")

    loaded_profiles: dict[str, ScenarioProfile] = {}
    for name, item in profiles.items():
        if not isinstance(item, dict):
            raise ValueError("each scenario profile must be a mapping")
        profile = ScenarioProfile(
            name=str(name).strip(),
            noise_ratio=float(item.get("noise_ratio", 0.0)),
            peak_hours=tuple(int(hour) for hour in item.get("peak_hours", [])),
            peak_multiplier=float(item.get("peak_multiplier", 1.0)),
            off_peak_multiplier=float(item.get("off_peak_multiplier", 1.0)),
            weekend_multiplier=float(item.get("weekend_multiplier", 1.0)),
            minimum_load_ratio=float(item.get("minimum_load_ratio", 0.0)),
        )
        loaded_profiles[profile.name] = profile
    return loaded_profiles


def _utc(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _stable_noise(seed_text: str) -> float:
    seed = 0
    for index, char in enumerate(seed_text):
        seed += (index + 1) * ord(char)
    return ((seed % 2001) / 1000.0) - 1.0


class LoadScenarioEngine:
    def __init__(self, profiles: dict[str, ScenarioProfile]) -> None:
        self.profiles = profiles

    def get_profile(self, profile_name: str) -> ScenarioProfile:
        try:
            return self.profiles[profile_name]
        except KeyError as error:
            raise ValueError(f"unknown scenario profile: {profile_name}") from error

    def calculate_active_power(self, device: LoadDevice, observed_at: datetime) -> float:
        profile = self.get_profile(device.config.scenario_profile)
        current_time = _utc(observed_at)

        base_kw = device.config.base_kw
        multiplier = profile.peak_multiplier if current_time.hour in profile.peak_hours else profile.off_peak_multiplier
        if current_time.weekday() >= 5:
            multiplier *= profile.weekend_multiplier

        noise_seed = f"{device.device_id}:{current_time:%Y%m%d%H%M}"
        noise_delta = 1.0 + (_stable_noise(noise_seed) * profile.noise_ratio)
        raw_power_kw = base_kw * multiplier * noise_delta
        shed_adjusted_kw = raw_power_kw * (1.0 - device.state.shed_ratio)

        minimum_kw = device.config.rated_kw * profile.minimum_load_ratio
        bounded_kw = min(device.config.rated_kw, max(minimum_kw, shed_adjusted_kw))
        return round(bounded_kw, 3)

    def build_measurement(self, device: LoadDevice, observed_at: datetime, elapsed_seconds: float | None = None) -> LoadMeasurement:
        current_time = _utc(observed_at)
        previous_time = device.state.last_updated_at.astimezone(timezone.utc)
        computed_elapsed_seconds = max((current_time - previous_time).total_seconds(), 0.0)
        duration_seconds = computed_elapsed_seconds if elapsed_seconds is None else max(elapsed_seconds, 0.0)

        next_p_kw = self.calculate_active_power(device, current_time)
        previous_kwh = device.measurement.kwh
        previous_kvarh = device.measurement.kvarh
        next_kwh = previous_kwh + (next_p_kw * (duration_seconds / 3600.0))

        measurement = LoadMeasurement.from_active_power(
            p_kw=next_p_kw,
            voltage_v=device.config.voltage_v,
            frequency_hz=device.config.frequency_hz,
            power_factor=device.config.power_factor,
            kwh=round(next_kwh, 6),
            kvarh=round(previous_kvarh + (next_p_kw * 0.1 * (duration_seconds / 3600.0)), 6),
            demand_max_kw=max(device.measurement.demand_max_kw, next_p_kw),
        )
        return measurement

    def tick_device(self, device: LoadDevice, observed_at: datetime | None = None, *, elapsed_seconds: float | None = None) -> LoadMeasurement:
        current_time = _utc(observed_at)
        measurement = self.build_measurement(device, current_time, elapsed_seconds=elapsed_seconds)
        device.apply_measurement(measurement, updated_at=current_time)
        return measurement

    def tick_fleet(self, fleet: LoadFleet, observed_at: datetime | None = None, *, elapsed_seconds: float | None = None) -> dict[str, LoadMeasurement]:
        current_time = _utc(observed_at)
        results: dict[str, LoadMeasurement] = {}
        for device in fleet.list_enabled():
            results[device.device_id] = self.tick_device(
                device,
                current_time,
                elapsed_seconds=elapsed_seconds,
            )
        return results
