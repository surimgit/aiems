from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class DeviceFileConfig(BaseModel):
    """Validated configuration loaded from config/devices.yaml."""

    plant_id: str
    device_id: str
    resource_type: str = Field(pattern=r"^ess$")
    publish_interval_sec: float = Field(gt=0)
    initial_soc: float = Field(ge=0, le=100)
    power_limit_kw: float = Field(gt=0)
    low_soc_threshold: float = Field(ge=0, le=100)
    high_soc_threshold: float = Field(ge=0, le=100)
    min_safe_soc_threshold: float = Field(ge=0, le=100)
    max_safe_soc_threshold: float = Field(ge=0, le=100)
    temperature_c: float = Field(default=25.0)
    max_temperature_c: float = Field(default=45.0)
    mqtt_broker_host: str = Field(default="localhost")
    mqtt_broker_port: int = Field(default=1883, ge=1, le=65535)

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


def load_config(path: Path) -> DeviceFileConfig:
    """Read YAML config and convert it into a validated config object."""

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")

    return DeviceFileConfig.model_validate(raw)
