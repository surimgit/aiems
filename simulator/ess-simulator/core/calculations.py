from __future__ import annotations

from typing import Literal


OperatingMode = Literal["charge", "discharge", "standby"]


# 운전 모드에 따라 ESS 유효전력 부호를 계산한다.
def calculate_signed_power(mode: OperatingMode, target_power_kw: float) -> float:
    if mode == "discharge":
        return target_power_kw
    if mode == "charge":
        return -target_power_kw
    return 0.0


# 한 tick 동안 SOC가 얼마나 변해야 하는지 계산한다.
def calculate_soc_delta(power_kw: float, interval_sec: float, power_limit_kw: float) -> float:
    interval_hours = interval_sec / 3600.0
    return (abs(power_kw) * interval_hours / power_limit_kw) * 100


# 한 tick 동안 누적 에너지가 얼마나 늘어나는지 계산한다.
def calculate_energy_increment(power_kw: float, interval_sec: float) -> float:
    interval_hours = interval_sec / 3600.0
    return abs(power_kw) * interval_hours
