from __future__ import annotations

from typing import Literal


# 현재 SOC와 온도 기준으로 충전이 가능한지 판단한다.
def ensure_charge_allowed(
    *,
    soc: float,
    temperature_c: float,
    high_soc_threshold: float,
    max_safe_soc_threshold: float,
    max_temperature_c: float,
) -> None:
    if soc >= high_soc_threshold:
        raise ValueError("Charging blocked: SOC is above high threshold")
    if soc >= max_safe_soc_threshold:
        raise ValueError("Charging blocked: SOC is above maximum safe threshold")
    if temperature_c >= max_temperature_c:
        raise ValueError("Charging blocked: temperature is above max temperature")


# 현재 SOC와 온도 기준으로 방전이 가능한지 판단한다.
def ensure_discharge_allowed(
    *,
    soc: float,
    temperature_c: float,
    low_soc_threshold: float,
    min_safe_soc_threshold: float,
    max_temperature_c: float,
) -> None:
    if soc <= low_soc_threshold:
        raise ValueError("Discharging blocked: SOC is below low threshold")
    if soc <= min_safe_soc_threshold:
        raise ValueError("Discharging blocked: SOC is below minimum safe threshold")
    if temperature_c >= max_temperature_c:
        raise ValueError("Discharging blocked: temperature is above max temperature")


# 현재 상태가 안전 정지로 강제 전환되어야 하는지 판단한다.
def evaluate_safety_transition(
    *,
    soc: float,
    temperature_c: float,
    operating_mode: Literal["charge", "discharge", "standby"],
    min_safe_soc_threshold: float,
    max_safe_soc_threshold: float,
    max_temperature_c: float,
) -> tuple[bool, bool]:
    if temperature_c >= max_temperature_c:
        return True, True

    if soc <= min_safe_soc_threshold and operating_mode == "discharge":
        return True, False

    if soc >= max_safe_soc_threshold and operating_mode == "charge":
        return True, False

    return False, False
