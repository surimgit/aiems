from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import elevation

from .load_service import LoadService
from .prediction_service import PredictionService


class ForecastService:
    def __init__(
        self,
        prediction_service: PredictionService | None = None,
        load_service: LoadService | None = None,
    ) -> None:
        self.prediction_service = prediction_service or PredictionService()
        self.load_service = load_service or LoadService()

    def forecast(self, payload: dict[str, Any]) -> dict[str, Any]:
        solar_payload = dict(payload.get("solar") or {})
        load_payload = dict(payload.get("load") or {})
        site_profile = payload.get("site_profile")

        if not solar_payload.get("features") and self._is_horizon_request(payload):
            solar_payload = self._build_solar_payload(payload)

        if not load_payload and self._is_horizon_request(payload):
            load_payload = self._build_load_payload(payload)

        if site_profile and "site_profile" not in load_payload:
            load_payload = {**load_payload, "site_profile": site_profile}

        solar_result = None
        if solar_payload.get("features"):
            solar_result = self.prediction_service.predict_capacity_factor(solar_payload)

        load_result = None
        if load_payload:
            load_result = self.load_service.predict_load(load_payload)

        forecasts = self._merge(solar_result, load_result)
        recommendations = self._recommend(forecasts, payload)
        return {
            "ok": True,
            "task": "forecast",
            "rows": len(forecasts),
            "forecasts": forecasts,
            "recommendations": recommendations,
            "solar_result": solar_result,
            "load_result": load_result,
        }

    @staticmethod
    def _is_horizon_request(payload: dict[str, Any]) -> bool:
        return bool(payload.get("target_times") or payload.get("start_time") or payload.get("periods"))

    def _build_solar_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        site = payload.get("site") or {}
        site_id = payload.get("site_id") or site.get("site_id")
        latitude = self._required_float(site, "latitude")
        longitude = self._required_float(site, "longitude")
        installed_capacity_kw = float(site.get("installed_capacity_kw") or payload.get("installed_capacity_kw"))
        timezone_name = site.get("timezone") or payload.get("timezone") or "Asia/Seoul"
        history = self._history_defaults(payload)
        features = []
        for target_time in self._target_times(payload, timezone_name):
            solar_elevation = self._solar_elevation(latitude, longitude, target_time)
            features.append(
                {
                    "target_time": target_time.isoformat(),
                    "site_id": site_id,
                    "region": site.get("region") or payload.get("region"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": timezone_name,
                    "installed_capacity_kw": installed_capacity_kw,
                    "solar_elevation_mid": solar_elevation,
                    "is_daylight": 1 if solar_elevation > 0 else 0,
                    **history,
                    **self._cyclical_features(target_time),
                }
            )
        return {
            "site_id": site_id,
            "region": site.get("region") or payload.get("region"),
            "installed_capacity_kw": installed_capacity_kw,
            "model_path": payload.get("solar_model_path"),
            "model_version": payload.get("solar_model_version"),
            "features": features,
        }

    def _build_load_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        site = payload.get("site") or {}
        timezone_name = site.get("timezone") or payload.get("timezone") or "Asia/Seoul"
        return {
            "site_id": payload.get("site_id") or site.get("site_id"),
            "site": site,
            "site_profile": payload.get("site_profile"),
            "timezone": timezone_name,
            "target_times": [target_time.isoformat() for target_time in self._target_times(payload, timezone_name)],
            "base_load_kw": payload.get("base_load_kw") or site.get("base_load_kw"),
            "min_load_kw": payload.get("min_load_kw", 0.0),
            "weather_weight": payload.get("weather_weight", 1.0),
            "reserve_ratio": payload.get("reserve_ratio"),
            "min_reserve_kw": payload.get("min_reserve_kw", 0.0),
        }

    @staticmethod
    def _target_times(payload: dict[str, Any], timezone_name: str) -> list[datetime]:
        if payload.get("target_times"):
            return [ForecastService._parse_time(value, timezone_name) for value in payload["target_times"]]
        if not payload.get("start_time"):
            raise ValueError("forecast horizon request requires start_time or target_times")
        start = ForecastService._parse_time(payload["start_time"], timezone_name)
        periods = int(payload.get("periods") or 24)
        step = timedelta(hours=float(payload.get("frequency_hours") or 1.0))
        return [start + step * index for index in range(periods)]

    @staticmethod
    def _parse_time(value: str, timezone_name: str) -> datetime:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
        return parsed

    @staticmethod
    def _required_float(site: dict[str, Any], key: str) -> float:
        if site.get(key) is None:
            raise ValueError(f"site.{key} is required for bundled forecast")
        return float(site[key])

    @staticmethod
    def _history_defaults(payload: dict[str, Any]) -> dict[str, float]:
        defaults = payload.get("history_defaults") or {}
        fallback = {
            "past_capacity_factor": 0.42,
            "past_capacity_factor_lag_1": 0.38,
            "past_capacity_factor_lag_24": 0.40,
            "rolling_mean_cf_3h": 0.35,
            "rolling_mean_cf_24h": 0.12,
        }
        return {name: float(defaults.get(name, value)) for name, value in fallback.items()}

    @staticmethod
    def _cyclical_features(target_time: datetime) -> dict[str, float]:
        hour = target_time.hour
        day_of_year = int(target_time.strftime("%j"))
        return {
            "hour_of_day_sin": math.sin(2 * math.pi * hour / 24.0),
            "hour_of_day_cos": math.cos(2 * math.pi * hour / 24.0),
            "day_of_year_sin": math.sin(2 * math.pi * day_of_year / 365.25),
            "day_of_year_cos": math.cos(2 * math.pi * day_of_year / 365.25),
        }

    @staticmethod
    def _solar_elevation(latitude: float, longitude: float, target_time: datetime) -> float:
        return float(elevation(Observer(latitude=latitude, longitude=longitude), target_time))

    @staticmethod
    def _merge(solar_result: dict[str, Any] | None, load_result: dict[str, Any] | None) -> list[dict[str, Any]]:
        by_time: dict[str, dict[str, Any]] = {}
        if solar_result:
            for item in solar_result.get("predictions", []):
                target_time = item.get("target_time")
                row = by_time.setdefault(target_time, {"target_time": target_time, "site_id": item.get("site_id")})
                row["predicted_solar_kw"] = item.get("predicted_generation_kw", item.get("predicted_solar_kw"))
                row["solar_confidence"] = item.get("confidence")
                row["solar_model_version"] = item.get("model_version")
        if load_result:
            for item in load_result.get("predictions", []):
                target_time = item.get("target_time")
                row = by_time.setdefault(target_time, {"target_time": target_time, "site_id": item.get("site_id")})
                if not row.get("site_id"):
                    row["site_id"] = item.get("site_id")
                row["predicted_load_kw"] = item.get("predicted_load_kw")
                row["safe_predicted_load_kw"] = item.get("safe_predicted_load_kw")
                row["load_model_version"] = item.get("model_version")
        for row in by_time.values():
            solar = float(row.get("predicted_solar_kw") or 0.0)
            load = float(row.get("safe_predicted_load_kw") or row.get("predicted_load_kw") or 0.0)
            row["predicted_net_load_kw"] = load - solar
        return [by_time[key] for key in sorted(by_time)]

    @staticmethod
    def _recommend(forecasts: list[dict[str, Any]], payload: dict[str, Any]) -> list[dict[str, Any]]:
        recommendations = []
        threshold = float(payload.get("net_load_high_threshold_kw", 0.0))
        for row in forecasts:
            net_load = float(row.get("predicted_net_load_kw") or 0.0)
            if threshold > 0 and net_load >= threshold:
                recommendations.append(
                    {
                        "target_time": row.get("target_time"),
                        "recommendation_type": "PREPARE_ESS_DISCHARGE",
                        "reason": "safe load minus solar forecast exceeds configured threshold",
                        "confidence": 0.75,
                        "requires_operator_approval": True,
                    }
                )
        return recommendations
