from __future__ import annotations

import math
import random
from dataclasses import dataclass

from core.profile_engine import GeneratedEssState, ProfileContext


@dataclass
class DefaultEssProfile:
    seed: int | None = None
    day_charge_bias_kw: float = 24.0
    evening_discharge_bias_kw: float = 18.0
    noise_ratio: float = 0.08
    temperature_noise_c: float = 0.35

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        self._last_power_kw = 0.0
        self._last_temp_c: float | None = None

    def generate(self, context: ProfileContext) -> GeneratedEssState:
        hour = context.sim_time.hour + (context.sim_time.minute / 60.0) + (context.sim_time.second / 3600.0)
        daytime_wave = math.cos((hour - 12.0) / 12.0 * math.pi)
        evening_wave = math.sin((hour - 18.0) / 8.0 * math.pi)

        charge_component = -max(0.0, daytime_wave) * self.day_charge_bias_kw
        discharge_component = max(0.0, evening_wave) * self.evening_discharge_bias_kw
        soc_centering = (context.soc - 50.0) / 50.0 * 6.0
        base_power_kw = charge_component + discharge_component + soc_centering

        jitter = context.power_limit_kw * self.noise_ratio * self._rng.uniform(-1.0, 1.0)
        smoothed_power = (self._last_power_kw * 0.82) + ((base_power_kw + jitter) * 0.18)

        if context.soc >= 96.0:
            smoothed_power = max(0.0, smoothed_power)
        elif context.soc <= 14.0:
            smoothed_power = min(0.0, smoothed_power)

        clamped_power = max(-context.power_limit_kw, min(context.power_limit_kw, smoothed_power))
        if abs(clamped_power) < 0.75:
            clamped_power = 0.0

        base_temp = 24.0 + abs(clamped_power) * 0.08
        if self._last_temp_c is None:
            self._last_temp_c = context.temperature_c
        next_temp = (self._last_temp_c * 0.88) + (base_temp * 0.12) + self._rng.uniform(-self.temperature_noise_c, self.temperature_noise_c)
        next_temp = max(18.0, min(42.0, next_temp))

        self._last_power_kw = clamped_power
        self._last_temp_c = next_temp
        return GeneratedEssState(
            power_kw=round(clamped_power, 3),
            temperature_c=round(next_temp, 3),
        )
