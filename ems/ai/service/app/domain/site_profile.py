from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


ALLOWED_USAGE_LEVELS = {"low", "medium", "high", "critical"}


def normalize_profile(profile: dict[str, Any], site: dict[str, Any], text: str) -> dict[str, Any]:
    profile.setdefault("schema_version", "site_profile.v1")
    profile.setdefault("site_id", site.get("site_id"))
    profile.setdefault("profile_version", site.get("profile_version", "v1"))
    profile.setdefault("site_type", "unknown")
    profile.setdefault("components", [])
    profile.setdefault("seasonal_adjustments", [])
    profile.setdefault("operational_constraints", [])
    profile.setdefault("forecast_context_features", {})
    profile.setdefault("assumptions", [])
    profile.setdefault("warnings", [])
    features = profile["forecast_context_features"]
    for name in ("weekday_load_bias", "weekend_load_bias", "night_load_bias", "summer_load_bias"):
        features[name] = float(features.get(name, 0.0))
    features.setdefault("critical_load_level", "medium")
    profile["_source"] = {
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return profile


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if profile.get("schema_version") != "site_profile.v1":
        errors.append("schema_version must be site_profile.v1")
    for key in ("site_id", "profile_version", "site_type"):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            errors.append(f"{key} must be a non-empty string")
    if not isinstance(profile.get("components"), list):
        errors.append("components must be a list")
    features = profile.get("forecast_context_features")
    if not isinstance(features, dict):
        errors.append("forecast_context_features must be an object")
    else:
        for name in ("weekday_load_bias", "weekend_load_bias", "night_load_bias", "summer_load_bias"):
            value = features.get(name)
            if not isinstance(value, (int, float)) or not -1.0 <= float(value) <= 1.0:
                errors.append(f"forecast_context_features.{name} must be numeric in [-1.0, 1.0]")
        if features.get("critical_load_level") not in ALLOWED_USAGE_LEVELS:
            errors.append("forecast_context_features.critical_load_level must be low|medium|high|critical")
    for key in ("seasonal_adjustments", "operational_constraints", "assumptions", "warnings"):
        if not isinstance(profile.get(key), list):
            errors.append(f"{key} must be a list")
    return errors


def profile_context_features(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    features = profile.get("forecast_context_features", {})
    if not isinstance(features, dict):
        return {}
    return {
        "profile_site_type": profile.get("site_type", "unknown"),
        "profile_weekday_load_bias": float(features.get("weekday_load_bias", 0.0)),
        "profile_weekend_load_bias": float(features.get("weekend_load_bias", 0.0)),
        "profile_night_load_bias": float(features.get("night_load_bias", 0.0)),
        "profile_summer_load_bias": float(features.get("summer_load_bias", 0.0)),
        "profile_critical_load_level": features.get("critical_load_level", "medium"),
    }

