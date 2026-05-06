from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo


CRITICAL_MULTIPLIER = {"low": 0.05, "medium": 0.10, "high": 0.15, "critical": 0.25}


class LoadService:
    def predict_load(self, payload: dict[str, Any]) -> dict[str, Any]:
        site = payload.get("site") or {}
        profile = payload.get("site_profile")
        targets = self._targets(payload)
        rows = []
        for target_time in targets:
            predicted, reasons = self._predict_one(payload, site, profile, target_time)
            reserve_ratio = self._reserve_ratio(profile, payload)
            reserve_kw = max(predicted * reserve_ratio, float(payload.get("min_reserve_kw", 0.0)))
            safe = predicted + reserve_kw
            rows.append(
                {
                    "target_time": target_time.isoformat(),
                    "site_id": payload.get("site_id") or site.get("site_id"),
                    "predicted_load_kw": predicted,
                    "safety_reserve_kw": reserve_kw,
                    "safe_predicted_load_kw": safe,
                    "fallback_flag": bool(payload.get("fallback_flag", True)),
                    "model_version": payload.get("model_version") or "load-prior-profile-v1.0.0",
                    "reason": ";".join(reasons) if reasons else "profile_prior",
                }
            )
        return {"ok": True, "task": "predict_load", "rows": len(rows), "predictions": rows}

    def _targets(self, payload: dict[str, Any]) -> list[datetime]:
        timezone_name = payload.get("timezone") or payload.get("site", {}).get("timezone", "Asia/Seoul")
        if payload.get("target_times"):
            return [self._parse_time(value, timezone_name) for value in payload["target_times"]]
        start = self._parse_time(payload.get("start_time"), timezone_name) if payload.get("start_time") else datetime.now(ZoneInfo(timezone_name))
        periods = int(payload.get("periods", 24))
        step = timedelta(hours=float(payload.get("frequency_hours", 1)))
        return [start + step * index for index in range(periods)]

    @staticmethod
    def _parse_time(value: str, timezone_name: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed

    def _predict_one(
        self,
        payload: dict[str, Any],
        site: dict[str, Any],
        profile: dict[str, Any] | None,
        target_time: datetime,
    ) -> tuple[float, list[str]]:
        base_load_kw = float(payload.get("base_load_kw") or site.get("base_load_kw") or 100.0)
        minimum = float(payload.get("min_load_kw", 0.0))
        hour_weight = self._hour_weight(target_time)
        profile_weight, reasons = self._profile_weight(profile, target_time)
        weather_weight = float(payload.get("weather_weight", 1.0))
        if weather_weight != 1.0:
            reasons.append(f"weather_weight={weather_weight:.2f}")
        predicted = max(minimum, base_load_kw * hour_weight * profile_weight * weather_weight)
        return float(predicted), reasons

    @staticmethod
    def _hour_weight(target_time: datetime) -> float:
        hour = target_time.hour
        if 8 <= hour <= 18:
            return 1.15
        if 0 <= hour <= 5:
            return 0.65
        if 19 <= hour <= 22:
            return 0.95
        return 0.8

    @staticmethod
    def _profile_weight(profile: dict[str, Any] | None, target_time: datetime) -> tuple[float, list[str]]:
        if not profile:
            return 1.0, []
        features = profile.get("forecast_context_features", {})
        weight = 1.0
        reasons: list[str] = []
        if target_time.weekday() < 5:
            bias = float(features.get("weekday_load_bias", 0.0))
            weight *= 1.0 + bias
            if bias:
                reasons.append(f"weekday_bias={bias:+.2f}")
        else:
            bias = float(features.get("weekend_load_bias", 0.0))
            weight *= 1.0 + bias
            if bias:
                reasons.append(f"weekend_bias={bias:+.2f}")
        if target_time.hour < 6 or target_time.hour >= 22:
            bias = float(features.get("night_load_bias", 0.0))
            weight *= 1.0 + bias
            if bias:
                reasons.append(f"night_bias={bias:+.2f}")
        if target_time.month in (6, 7, 8, 9):
            bias = float(features.get("summer_load_bias", 0.0))
            weight *= 1.0 + bias
            if bias:
                reasons.append(f"summer_bias={bias:+.2f}")
        return max(0.2, weight), reasons

    @staticmethod
    def _reserve_ratio(profile: dict[str, Any] | None, payload: dict[str, Any]) -> float:
        if payload.get("reserve_ratio") is not None:
            return float(payload["reserve_ratio"])
        level = "medium"
        if profile:
            level = profile.get("forecast_context_features", {}).get("critical_load_level", "medium")
        return CRITICAL_MULTIPLIER.get(level, 0.10)
