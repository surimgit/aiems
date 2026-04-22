from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class ProfileContext:
    sim_time: datetime
    publish_interval_sec: float
    soc: float
    power_limit_kw: float
    capacity_kwh: float
    temperature_c: float
    device_id: str


@dataclass
class GeneratedEssState:
    power_kw: float
    temperature_c: float


class EssProfile(Protocol):
    def generate(self, context: ProfileContext) -> GeneratedEssState:
        ...
