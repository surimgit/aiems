from __future__ import annotations

import math
from typing import Any

import requests

from ..config import settings


MODEL_REGION_CENTER = {
    "서울시": (37.5665, 126.9780),
    "부산시": (35.1796, 129.0756),
    "대전시": (36.3504, 127.3845),
    "울산시": (35.5384, 129.3114),
    "제주도": (33.4996, 126.5312),
}


class StateSiteMetadataClient:
    def __init__(self, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    def fetch(self, site_id: str, current: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not settings.state_api_base_url:
            return None

        url = f"{settings.state_api_base_url.rstrip('/')}/api/plants/{site_id}/state"
        response = self.session.get(url, timeout=settings.state_api_timeout_seconds)
        response.raise_for_status()
        body = response.json()
        resources = body.get("resources") if isinstance(body, dict) else None
        if not isinstance(resources, list):
            return None

        solar_resources = [
            item for item in resources
            if str(item.get("resource_type") or "").upper() in {"SOLAR", "PV"}
        ]
        if not solar_resources:
            return None

        latitude, longitude = self._solar_center(solar_resources)
        installed_capacity_kw = self._installed_capacity_kw(solar_resources)
        metadata = self._merged_resource_metadata(solar_resources)
        model_region = (
            self._optional_str(metadata.get("model_region"))
            or self._optional_str((current or {}).get("model_region"))
            or self._nearest_model_region(latitude, longitude)
        )
        region = (
            self._optional_str(metadata.get("region"))
            or self._optional_str(metadata.get("address_region"))
            or self._optional_str((current or {}).get("region"))
            or model_region
        )
        if latitude is None or longitude is None or installed_capacity_kw is None or region is None:
            return None

        return {
            "site_id": site_id,
            "region": region,
            "model_region": model_region,
            "dong_code": self._optional_str(metadata.get("dong_code")) or self._optional_str((current or {}).get("dong_code")),
            "latitude": latitude,
            "longitude": longitude,
            "installed_capacity_kw": installed_capacity_kw,
            "timezone": (
                self._optional_str(metadata.get("timezone"))
                or self._optional_str((current or {}).get("timezone"))
                or "Asia/Seoul"
            ),
            "model_capacity_kw": self._optional_float(metadata.get("model_capacity_kw"))
            or self._optional_float((current or {}).get("model_capacity_kw"))
            or 100000.0,
        }

    @classmethod
    def _solar_center(cls, resources: list[dict[str, Any]]) -> tuple[float | None, float | None]:
        weighted_lat = 0.0
        weighted_lon = 0.0
        total_weight = 0.0
        plain_lat = []
        plain_lon = []
        for item in resources:
            lat = cls._optional_float(item.get("latitude"))
            lon = cls._optional_float(item.get("longitude"))
            if lat is None or lon is None:
                continue
            weight = cls._resource_capacity_kw(item) or 0.0
            if weight > 0:
                weighted_lat += lat * weight
                weighted_lon += lon * weight
                total_weight += weight
            plain_lat.append(lat)
            plain_lon.append(lon)

        if total_weight > 0:
            return weighted_lat / total_weight, weighted_lon / total_weight
        if plain_lat and plain_lon:
            return sum(plain_lat) / len(plain_lat), sum(plain_lon) / len(plain_lon)
        return None, None

    @classmethod
    def _installed_capacity_kw(cls, resources: list[dict[str, Any]]) -> float | None:
        values = [cls._resource_capacity_kw(item) for item in resources]
        numeric_values = [value for value in values if value is not None and value > 0]
        if not numeric_values:
            return None
        return sum(numeric_values)

    @classmethod
    def _resource_capacity_kw(cls, item: dict[str, Any]) -> float | None:
        telemetry = item.get("telemetry") if isinstance(item.get("telemetry"), dict) else {}
        site_metadata = item.get("site_metadata") if isinstance(item.get("site_metadata"), dict) else {}
        for source in (item, telemetry, site_metadata):
            value = cls._first_present(
                source,
                (
                    "installed_capacity_kw",
                    "installedCapacityKw",
                    "capacity_kw",
                    "capacityKw",
                    "rated_power_kw",
                    "ratedPowerKw",
                    "rated_capacity_kw",
                    "ratedCapacityKw",
                    "max_power_kw",
                    "maxPowerKw",
                    "power_limit_kw",
                    "powerLimitKw",
                ),
            )
            numeric_value = cls._optional_float(value)
            if numeric_value is not None and numeric_value > 0:
                return numeric_value
        return None

    @classmethod
    def _merged_resource_metadata(cls, resources: list[dict[str, Any]]) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        aliases = {
            "region": ("region",),
            "address_region": ("address_region", "addressRegion"),
            "model_region": ("model_region", "modelRegion"),
            "dong_code": ("dong_code", "dongCode", "dong_cd", "dongCd", "adm_cd", "admCd"),
            "timezone": ("timezone", "time_zone", "timeZone"),
            "model_capacity_kw": ("model_capacity_kw", "modelCapacityKw", "estimated_capacity_kw", "estimatedCapacityKw"),
        }
        for item in resources:
            for source in (
                item.get("site_metadata") if isinstance(item.get("site_metadata"), dict) else {},
                item.get("location") if isinstance(item.get("location"), dict) else {},
            ):
                for key, names in aliases.items():
                    value = cls._first_present(source, names)
                    if key not in merged and value not in (None, ""):
                        merged[key] = value
        return merged

    @staticmethod
    def _nearest_model_region(latitude: float | None, longitude: float | None) -> str | None:
        if latitude is None or longitude is None:
            return None
        best_region = None
        best_distance = None
        for region, (center_lat, center_lon) in MODEL_REGION_CENTER.items():
            distance = math.hypot(latitude - center_lat, longitude - center_lon)
            if best_distance is None or distance < best_distance:
                best_region = region
                best_distance = distance
        return best_region

    @staticmethod
    def _first_present(source: dict[str, Any], keys: tuple[str, ...]) -> Any:
        if not isinstance(source, dict):
            return None
        for key in keys:
            value = source.get(key)
            if value is not None and value != "":
                return value
        return None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
