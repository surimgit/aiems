from __future__ import annotations

import unittest

from core.calculations import (
    apply_soc_delta,
    calculate_energy_delta_kwh,
    calculate_interval_hours,
    calculate_signed_power,
    calculate_soc_delta,
    clamp_soc,
)


class CalculationsUnitTest(unittest.TestCase):
    def test_calculate_interval_hours_converts_seconds_to_hours(self) -> None:
        """tick 간격은 초에서 시간으로 정확히 변환되어야 한다."""
        self.assertAlmostEqual(calculate_interval_hours(900.0), 0.25)

    def test_calculate_energy_delta_kwh_uses_absolute_power(self) -> None:
        """충전과 방전 모두 이동 에너지량은 절대값 기준으로 계산한다."""
        self.assertAlmostEqual(calculate_energy_delta_kwh(-50.0, 3600.0), 50.0)
        self.assertAlmostEqual(calculate_energy_delta_kwh(20.0, 1800.0), 10.0)

    def test_calculate_soc_delta_uses_capacity_kwh(self) -> None:
        """SOC 변화율은 이동 에너지와 배터리 용량으로 계산해야 한다."""
        self.assertAlmostEqual(calculate_soc_delta(25.0, 500.0), 5.0)

    def test_apply_soc_delta_respects_operating_mode(self) -> None:
        """충전은 증가, 방전은 감소, 대기는 유지되어야 한다."""
        self.assertAlmostEqual(apply_soc_delta(40.0, 5.0, "charge"), 45.0)
        self.assertAlmostEqual(apply_soc_delta(40.0, 5.0, "discharge"), 35.0)
        self.assertAlmostEqual(apply_soc_delta(40.0, 5.0, "standby"), 40.0)

    def test_clamp_soc_limits_result_to_valid_range(self) -> None:
        """계산 결과가 경계를 넘어도 SOC는 0~100으로 고정되어야 한다."""
        self.assertEqual(clamp_soc(-3.0), 0.0)
        self.assertEqual(clamp_soc(102.5), 100.0)

    def test_calculate_signed_power_keeps_ess_sign_convention(self) -> None:
        """ESS는 방전 양수, 충전 음수 규칙을 유지해야 한다."""
        self.assertEqual(calculate_signed_power("discharge", 15.0), 15.0)
        self.assertEqual(calculate_signed_power("charge", 15.0), -15.0)
        self.assertEqual(calculate_signed_power("standby", 15.0), 0.0)


if __name__ == "__main__":
    unittest.main()
