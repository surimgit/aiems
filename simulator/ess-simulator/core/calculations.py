from __future__ import annotations

from typing import Literal


OperatingMode = Literal["charge", "discharge", "standby"]

# 충방전 효율 — 실제 리튬이온 배터리 기준 (충전 95%, 방전 95%)
_CHARGE_EFFICIENCY = 0.95
_DISCHARGE_EFFICIENCY = 0.95


# 운전 모드에 따라 ESS 유효전력 부호를 계산한다.
def calculate_signed_power(mode: OperatingMode, target_power_kw: float) -> float:
    if mode == "discharge":
        return target_power_kw
    if mode == "charge":
        return -target_power_kw
    return 0.0


# 초 단위 tick 간격을 시간 단위로 바꾼다.
def calculate_interval_hours(interval_sec: float) -> float:
    return interval_sec / 3600.0


# 현재 전력과 tick 간격으로 이동한 에너지량을 계산한다.
def calculate_energy_delta_kwh(power_kw: float, interval_sec: float) -> float:
    return abs(power_kw) * calculate_interval_hours(interval_sec)


# 이동한 에너지량을 SOC 변화율로 환산한다. 충방전 효율 반영.
def calculate_soc_delta(energy_delta_kwh: float, capacity_kwh: float, mode: OperatingMode = "discharge") -> float:
    if mode == "charge":
        # 충전: 실제 저장량 = 투입 에너지 × 효율
        effective_energy = energy_delta_kwh * _CHARGE_EFFICIENCY
    else:
        # 방전: 실제 소모량 = 방전 에너지 ÷ 효율 (배터리가 더 많이 소모)
        effective_energy = energy_delta_kwh / _DISCHARGE_EFFICIENCY
    return (effective_energy / capacity_kwh) * 100.0


# 충전과 방전 모드에 따라 SOC를 증감시킨다.
def apply_soc_delta(current_soc: float, soc_delta: float, mode: OperatingMode) -> float:
    if mode == "charge":
        return current_soc + soc_delta
    if mode == "discharge":
        return current_soc - soc_delta
    return current_soc


# SOC는 항상 0~100 범위에 머물도록 보정한다.
def clamp_soc(value: float) -> float:
    return max(0.0, min(100.0, value))


# 누적 에너지는 throughput 개념으로 절대량을 더한다.
def calculate_energy_increment(power_kw: float, interval_sec: float) -> float:
    return calculate_energy_delta_kwh(power_kw, interval_sec)
