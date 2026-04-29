from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


DEFAULT_IRRADIANCE_THRESHOLD = 10.0


def _value(row: dict[str, Any], names: tuple[str, ...], default: float | None = None) -> float | None:
    for name in names:
        value = row.get(name)
        if value is None:
            continue
        try:
            if pd.isna(value):
                continue
        except TypeError:
            pass
        return float(value)
    return default


def is_night_or_low_sun(
    row: dict[str, Any],
    irradiance_threshold: float = DEFAULT_IRRADIANCE_THRESHOLD,
) -> bool:
    daylight_flag = _value(row, ("is_daylight", "daylight_flag"))
    if daylight_flag is not None:
        return daylight_flag <= 0.0

    solar_elevation = _value(row, ("solar_elevation", "solar_elevation_deg"))
    if solar_elevation is not None:
        return solar_elevation <= 0.0

    # Only use an explicitly engineered irradiance estimate for hard zero-clamp.
    # Raw training columns named "irradiance" may be normalized, missing, or
    # shifted relative to the target horizon, so they are model features rather
    # than safety signals.
    estimated_irradiance = _value(row, ("estimated_irradiance",))
    if estimated_irradiance is not None:
        return estimated_irradiance <= irradiance_threshold

    hour = _value(row, ("target_hour", "hour", "hour_of_day"))
    if hour is not None:
        return hour < 6 or hour > 19

    return False


def postprocess_solar_prediction(
    raw_prediction_kw: float,
    feature_row: dict[str, Any],
    installed_capacity_kw: float | None = None,
    irradiance_threshold: float = DEFAULT_IRRADIANCE_THRESHOLD,
) -> dict[str, Any]:
    reasons: list[str] = []
    prediction = float(raw_prediction_kw)

    if is_night_or_low_sun(feature_row, irradiance_threshold=irradiance_threshold):
        prediction = 0.0
        reasons.append("night_zero_clamp")

    if prediction < 0.0:
        prediction = 0.0
        reasons.append("negative_clamp")

    capacity = installed_capacity_kw
    if capacity is None:
        capacity = _value(feature_row, ("installed_capacity_kw", "capacity_kw"))

    if capacity is not None and capacity > 0 and prediction > capacity:
        prediction = float(capacity)
        reasons.append("capacity_clamp")

    return {
        "raw_predicted_solar_kw": float(raw_prediction_kw),
        "predicted_solar_kw": float(prediction),
        "postprocess_reason": ",".join(reasons) if reasons else "none",
    }


def postprocess_solar_predictions(
    frame: pd.DataFrame,
    raw_predictions,
    installed_capacity_kw: float | None = None,
    irradiance_threshold: float = DEFAULT_IRRADIANCE_THRESHOLD,
) -> pd.DataFrame:
    raw_array = np.asarray(raw_predictions, dtype=float)
    rows = []
    for index, raw_prediction in enumerate(raw_array):
        rows.append(
            postprocess_solar_prediction(
                float(raw_prediction),
                frame.iloc[index].to_dict(),
                installed_capacity_kw=installed_capacity_kw,
                irradiance_threshold=irradiance_threshold,
            )
        )
    return pd.DataFrame(rows, index=frame.index)
