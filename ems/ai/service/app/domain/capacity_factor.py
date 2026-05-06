from __future__ import annotations

from typing import Any

import pandas as pd


def capacity_kw(payload: dict[str, Any], source: dict[str, Any]) -> float:
    value = source.get("installed_capacity_kw", payload.get("installed_capacity_kw"))
    if value is None:
        value = source.get("estimated_capacity_wh", payload.get("estimated_capacity_wh"))
        if value is not None:
            value = float(value) / 1000.0
    if value is None:
        raise ValueError("installed_capacity_kw is required for capacity-factor prediction")
    capacity = float(value)
    if capacity <= 0:
        raise ValueError(f"installed_capacity_kw must be positive: {capacity}")
    return capacity


def is_night_for_capacity_factor(source: dict[str, Any]) -> bool:
    for name in ("is_daylight", "daylight_flag"):
        value = source.get(name)
        if value is not None and not pd.isna(value):
            return float(value) <= 0.0
    for name in ("solar_elevation_mid", "solar_elevation", "solar_elevation_deg"):
        value = source.get(name)
        if value is not None and not pd.isna(value):
            return float(value) <= 0.0
    return False

