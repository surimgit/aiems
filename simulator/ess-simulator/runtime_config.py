from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class ProfileConfig(BaseModel):
    module: str = "core.profiles.default_profile"
    class_name: str = "DefaultEssProfile"
    seed: int | None = None


class DeviceConfig(BaseModel):
    device_id: str
    resource_type: str = Field(pattern=r"^ess$")
    publish_interval_sec: float = Field(gt=0)
    initial_soc: float = Field(ge=0, le=100)
    power_limit_kw: float = Field(gt=0)
    capacity_kwh: float = Field(gt=0)
    low_soc_threshold: float = Field(ge=0, le=100)
    high_soc_threshold: float = Field(ge=0, le=100)
    min_safe_soc_threshold: float = Field(ge=0, le=100)
    max_safe_soc_threshold: float = Field(ge=0, le=100)
    temperature_c: float = Field(default=25.0)
    max_temperature_c: float = Field(default=45.0)
    profile: ProfileConfig = Field(default_factory=ProfileConfig)

    @field_validator("high_soc_threshold")
    @classmethod
    def validate_high_threshold(cls, value: float, info) -> float:
        low = info.data.get("low_soc_threshold")
        if low is not None and value <= low:
            raise ValueError("high_soc_threshold must be greater than low_soc_threshold")
        return value

    @field_validator("max_safe_soc_threshold")
    @classmethod
    def validate_max_safe_threshold(cls, value: float, info) -> float:
        min_safe = info.data.get("min_safe_soc_threshold")
        if min_safe is not None and value <= min_safe:
            raise ValueError("max_safe_soc_threshold must be greater than min_safe_soc_threshold")
        return value


class RuntimeConfig(BaseModel):
    plant_id: str
    mqtt_broker_host: str = Field(default="localhost")
    mqtt_broker_port: int = Field(default=1883, ge=1, le=65535)
    devices: list[DeviceConfig]


def _coerce_legacy_config(raw: dict) -> dict:
    if "devices" in raw:
        return raw

    legacy_device_keys = {
        "device_id",
        "resource_type",
        "publish_interval_sec",
        "initial_soc",
        "power_limit_kw",
        "capacity_kwh",
        "low_soc_threshold",
        "high_soc_threshold",
        "min_safe_soc_threshold",
        "max_safe_soc_threshold",
        "temperature_c",
        "max_temperature_c",
    }
    device = {key: value for key, value in raw.items() if key in legacy_device_keys}
    return {
        "plant_id": raw["plant_id"],
        "mqtt_broker_host": raw.get("mqtt_broker_host", "localhost"),
        "mqtt_broker_port": raw.get("mqtt_broker_port", 1883),
        "devices": [device],
    }


def load_config(path: Path) -> RuntimeConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")

    return RuntimeConfig.model_validate(_coerce_legacy_config(raw))
