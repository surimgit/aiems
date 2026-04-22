from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class ScenarioProfile:
    name: str
    noise_ratio: float
    peak_hours: tuple[int, ...]
    peak_multiplier: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("scenario profile name is required")
        if self.noise_ratio < 0:
            raise ValueError("noise_ratio must be greater than or equal to 0")
        if self.peak_multiplier < 1:
            raise ValueError("peak_multiplier must be greater than or equal to 1")
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
        )
        loaded_profiles[profile.name] = profile
    return loaded_profiles
