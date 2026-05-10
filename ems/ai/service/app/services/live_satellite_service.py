from __future__ import annotations

import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import requests
from astral import Observer
from astral.sun import elevation

from ..config import AI_ROOT, settings
from ..runtime import clean_env_value, env_str
from .runpod_client import RunpodClient

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - python-dotenv is in service requirements.
    load_dotenv = None


KST = ZoneInfo("Asia/Seoul")
GRID_WIDTH = 149
GRID_HEIGHT = 253
MISSING_UINT8 = np.uint8(255)

KMA_XY_LONLAT_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_xy_lonlat"
KMA_ULTRA_FORECAST_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_vsrt_grd"
KMA_ULTRA_NOWCAST_URL = "https://apihub.kma.go.kr/api/typ01/cgi-bin/url/nph-dfs_odam_grd"
GK2A_CLA_AREA_URL = "https://apihub.kma.go.kr/api/typ02/openApi/CloudSatlitInfoService/getGk2aclaArea"
GK2A_CLD_AREA_URL = "https://apihub.kma.go.kr/api/typ02/openApi/CloudSatlitInfoService/getGk2acldArea"

REGION_CENTER = {
    "서울시": (37.5665, 126.9780),
    "부산시": (35.1796, 129.0756),
    "대전시": (36.3504, 127.3845),
    "울산시": (35.5384, 129.3114),
    "제주도": (33.4996, 126.5312),
}

REGION_DONG_CODE = {
    "서울시": "1100000000",
    "부산시": "2600000000",
    "대전시": "3000000000",
    "울산시": "3100000000",
    "제주도": "5000000000",
}

REGION_ALIASES = {
    "seoul": "서울시",
    "서울": "서울시",
    "busan": "부산시",
    "부산": "부산시",
    "daejeon": "대전시",
    "대전": "대전시",
    "ulsan": "울산시",
    "울산": "울산시",
    "jeju": "제주도",
    "제주": "제주도",
}

# This is a model-side scale feature, not the user's PV capacity.
# Keep the operational default stable unless the caller passes a calibrated value.
DEFAULT_MODEL_CAPACITY_KW = 100000.0


@dataclass(frozen=True)
class GridPoint:
    longitude: float
    latitude: float
    x: int
    y: int


@dataclass(frozen=True)
class WeatherSnapshot:
    source: str
    tmfc: str | None
    tmef: str | None
    values: dict[str, float | None]
    warnings: list[str]


class LiveSatellitePredictionService:
    def __init__(
        self,
        prediction_service: Any,
        *,
        session: requests.Session | None = None,
        runpod_client: RunpodClient | None = None,
    ) -> None:
        self.prediction_service = prediction_service
        self.session = session or requests.Session()
        self.runpod_client = runpod_client or RunpodClient()

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = dict(payload)
        payload["region"] = self._normalize_region(payload.get("region"))
        if self.runpod_client.enabled:
            return self.runpod_client.run_sync("predict_live_satellite_capacity_factor", payload)

        key = self._auth_key()
        warnings: list[str] = []

        region = str(payload["region"])
        if region not in REGION_CENTER:
            raise ValueError(f"Unsupported live satellite region: {region}")

        latitude, longitude = self._site_lat_lon(payload, region)
        dong_code = str(payload.get("dong_code") or REGION_DONG_CODE[region])
        horizon_hours = int(self._float(payload.get("horizon_hours"), 1.0))
        if not 1 <= horizon_hours <= 24:
            raise ValueError("horizon_hours must be between 1 and 24 for the satellite model")

        now_kst = datetime.now(KST).replace(second=0, microsecond=0)
        target_time = self._target_time(payload.get("target_time"), now_kst, horizon_hours)
        solar_elevation = self._solar_elevation(latitude, longitude, target_time)

        grid = self._resolve_grid(longitude, latitude, key)
        weather = self._fetch_weather(
            grid,
            target_time,
            now_kst,
            key,
            search_hours=int(self._float(payload.get("weather_search_hours"), 6.0)),
        )
        warnings.extend(weather.warnings)

        satellite_records, satellite_warnings = self._fetch_satellite_sequence(
            dong_code,
            now_kst,
            key,
            search_hours=int(self._float(payload.get("satellite_search_hours"), 12.0)),
        )
        warnings.extend(satellite_warnings)

        images, satellite_summary, proxy_warnings = self._build_proxy_images(satellite_records, weather.values)
        warnings.extend(proxy_warnings)
        installed_capacity_kw = self._float(payload.get("installed_capacity_kw"), 100.0)
        model_capacity_kw = self._float(
            payload.get("model_capacity_kw", payload.get("estimated_capacity_kw")),
            DEFAULT_MODEL_CAPACITY_KW,
        )

        feature = {
            "site_id": payload.get("site_id"),
            "region": region,
            "target_time": target_time.isoformat(),
            "horizon_hours": horizon_hours,
            "installed_capacity_kw": installed_capacity_kw,
            "estimated_capacity_kw": model_capacity_kw,
            "solar_elevation": solar_elevation,
            "is_daylight": 1.0 if solar_elevation > 0.0 else 0.0,
            "wind_speed_ms": self._value(weather.values, "WSD", 0.0),
            "wind_dir_deg": self._value(weather.values, "VEC", 0.0),
            "temperature_c": self._value(weather.values, "T1H", self._value(weather.values, "TMP", 15.0)),
            "humidity_pct": self._value(weather.values, "REH", 60.0),
            "rainfall_mm": self._value(weather.values, "RN1", self._value(weather.values, "PCP", 0.0)),
            "images": images.tolist(),
        }

        prediction_payload = {
            "site_id": payload.get("site_id"),
            "region": region,
            "installed_capacity_kw": installed_capacity_kw,
            "model_version": payload.get("model_version"),
            "model_path": payload.get("model_path") or settings.default_satellite_model_path,
            "device": payload.get("device"),
            "image_normalization": payload.get("image_normalization") or "binary",
            "max_capacity_factor": payload.get("max_capacity_factor") or settings.default_max_capacity_factor,
            "features": [feature],
        }
        prediction_result = self.prediction_service.predict_satellite_capacity_factor(prediction_payload)

        return {
            "ok": True,
            "task": "predict_live_satellite_capacity_factor",
            "input_mode": "gk2a_area_proxy",
            "warnings": warnings,
            "site": {
                "site_id": payload.get("site_id"),
                "region": region,
                "latitude": latitude,
                "longitude": longitude,
                "dong_code": dong_code,
                "grid": grid.__dict__,
            },
            "target": {
                "target_time": target_time.isoformat(),
                "horizon_hours": horizon_hours,
                "solar_elevation": solar_elevation,
                "is_daylight": solar_elevation > 0.0,
                "installed_capacity_kw": installed_capacity_kw,
                "model_capacity_kw": model_capacity_kw,
            },
            "weather": {
                "source": weather.source,
                "tmfc": weather.tmfc,
                "tmef": weather.tmef,
                "values": weather.values,
            },
            "satellite": {
                "source": "kma_apihub_gk2a_area",
                "mode": "scalar_area_to_64x64_proxy",
                "image_shape": list(images.shape),
                "channels": ["CA", "CF_PROXY", "CT_PROXY", "CLD"],
                "frames": satellite_summary,
            },
            "model_input": {
                "numeric_feature_values": {key: value for key, value in feature.items() if key != "images"},
                "image_summary": self._image_summary(images),
            },
            "prediction": prediction_result["predictions"][0],
            "prediction_result": prediction_result,
        }

    @staticmethod
    def _load_env_file(env_file: Path) -> None:
        if not env_file.exists():
            return
        if load_dotenv is not None:
            load_dotenv(env_file, override=False)
            return
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))

    def _auth_key(self) -> str:
        self._load_env_file(AI_ROOT / ".env")
        env_name = "KMA_AUTH_KEY"
        value = env_str(env_name)
        if not value:
            raise RuntimeError(f"Environment variable {env_name} is not set")
        return value

    @staticmethod
    def _float(value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, str):
            text = clean_env_value(value) or ""
            if not text or text in {"-", "강수없음", "없음"}:
                return default
            if text.startswith("1mm 미만"):
                return 0.5
            value = text.replace("mm", "").strip()
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if math.isnan(parsed):
            return default
        return parsed

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        parsed = LiveSatellitePredictionService._float(value, float("nan"))
        if math.isnan(parsed):
            return None
        return parsed

    @staticmethod
    def _value(values: dict[str, float | None], name: str, default: float) -> float:
        value = values.get(name)
        return default if value is None else float(value)

    @staticmethod
    def _normalize_region(value: Any) -> str:
        text = str(value or "대전시").strip()
        return REGION_ALIASES.get(text.lower(), text)

    @staticmethod
    def _site_lat_lon(payload: dict[str, Any], region: str) -> tuple[float, float]:
        default_lat, default_lon = REGION_CENTER[region]
        return (
            LiveSatellitePredictionService._float(payload.get("latitude"), default_lat),
            LiveSatellitePredictionService._float(payload.get("longitude"), default_lon),
        )

    @staticmethod
    def _target_time(value: Any, now_kst: datetime, horizon_hours: int) -> datetime:
        if value:
            text = str(value).strip().replace("Z", "+00:00")
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=KST)
            return parsed.astimezone(KST)
        base = now_kst.replace(minute=0)
        return base + timedelta(hours=horizon_hours)

    @staticmethod
    def _solar_elevation(latitude: float, longitude: float, target_time: datetime) -> float:
        midpoint = target_time.astimezone(KST) - timedelta(minutes=30)
        return float(elevation(Observer(latitude=latitude, longitude=longitude), midpoint))

    def _request_text(self, url: str, params: dict[str, Any], key: str, *, timeout: int = 30) -> str:
        request_params = {**params, "authKey": key}
        response = self.session.get(url, params=request_params, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"KMA API HTTP {response.status_code}")
        return response.text

    def _request_json(self, url: str, params: dict[str, Any], key: str, *, timeout: int = 30) -> dict[str, Any]:
        request_params = {**params, "authKey": key}
        response = self.session.get(url, params=request_params, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError(f"KMA API HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("KMA API returned non-JSON payload") from exc

    def _resolve_grid(self, longitude: float, latitude: float, key: str) -> GridPoint:
        text = self._request_text(
            KMA_XY_LONLAT_URL,
            {"lon": longitude, "lat": latitude, "help": 0},
            key,
        )
        data_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        if not data_lines:
            raise RuntimeError("KMA grid conversion returned no coordinate row")
        parts = [part.strip() for part in data_lines[0].split(",")]
        if len(parts) != 4:
            parts = data_lines[0].split()
        if len(parts) < 4:
            raise RuntimeError(f"Unexpected KMA grid conversion row: {data_lines[0]}")
        return GridPoint(
            longitude=float(parts[0]),
            latitude=float(parts[1]),
            x=int(float(parts[2])),
            y=int(float(parts[3])),
        )

    @staticmethod
    def _parse_grid_values(text: str) -> list[float]:
        data_text = "\n".join(
            line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
        )
        values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", data_text)]
        expected = GRID_WIDTH * GRID_HEIGHT
        if len(values) != expected:
            raise RuntimeError(f"KMA grid payload expected {expected} values, found {len(values)}")
        return values

    @staticmethod
    def _grid_value_at(values: list[float], x: int, y: int) -> float | None:
        if not (1 <= x <= GRID_WIDTH and 1 <= y <= GRID_HEIGHT):
            raise RuntimeError(f"KMA grid coordinate out of range: x={x}, y={y}")
        value = float(values[(y - 1) * GRID_WIDTH + (x - 1)])
        return None if value <= -90.0 else value

    def _fetch_grid_variable(
        self,
        url: str,
        variable: str,
        grid: GridPoint,
        key: str,
        *,
        tmfc: str,
        tmef: str | None = None,
    ) -> float | None:
        params: dict[str, Any] = {"tmfc": tmfc, "vars": variable}
        if tmef:
            params["tmef"] = tmef
        text = self._request_text(url, params, key)
        values = self._parse_grid_values(text)
        return self._grid_value_at(values, grid.x, grid.y)

    def _fetch_weather(
        self,
        grid: GridPoint,
        target_time: datetime,
        now_kst: datetime,
        key: str,
        *,
        search_hours: int,
    ) -> WeatherSnapshot:
        warnings: list[str] = []
        variables = ["T1H", "RN1", "VEC", "WSD", "REH", "SKY", "PTY"]
        tmef = target_time.strftime("%Y%m%d%H")
        base = now_kst.replace(minute=0, second=0, microsecond=0)

        for offset in range(max(0, search_hours) + 1):
            tmfc = (base - timedelta(hours=offset)).strftime("%Y%m%d%H%M")
            values: dict[str, float | None] = {}
            failures = 0
            for variable in variables:
                try:
                    values[variable] = self._fetch_grid_variable(
                        KMA_ULTRA_FORECAST_URL,
                        variable,
                        grid,
                        key,
                        tmfc=tmfc,
                        tmef=tmef,
                    )
                    time.sleep(0.05)
                except Exception:
                    values[variable] = None
                    failures += 1
            if values.get("WSD") is not None and values.get("VEC") is not None:
                if failures:
                    warnings.append(f"ultra_srt_fcst_partial_missing:{tmfc}")
                return WeatherSnapshot("ultra_srt_fcst", tmfc, tmef, values, warnings)
            warnings.append(f"ultra_srt_fcst_no_data:{tmfc}")

        nowcast_vars = ["T1H", "RN1", "VEC", "WSD", "REH", "PTY"]
        tmfc = base.strftime("%Y%m%d%H%M")
        values = {name: None for name in variables}
        for variable in nowcast_vars:
            try:
                values[variable] = self._fetch_grid_variable(
                    KMA_ULTRA_NOWCAST_URL,
                    variable,
                    grid,
                    key,
                    tmfc=tmfc,
                )
                time.sleep(0.05)
            except Exception:
                values[variable] = None
        warnings.append("ultra_srt_fcst_fallback_to_nowcast")
        return WeatherSnapshot("ultra_srt_ncst", tmfc, None, values, warnings)

    @staticmethod
    def _json_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = payload.get("response", {})
        header = response.get("header", {})
        result_code = header.get("resultCode")
        if result_code not in (None, "00"):
            return []
        items = response.get("body", {}).get("items", {}).get("item", [])
        if isinstance(items, dict):
            return [items]
        return [item for item in items if isinstance(item, dict)]

    def _fetch_gk2a_value(self, url: str, result_type: str, date_time: str, dong_code: str, key: str) -> dict[str, Any] | None:
        payload = self._request_json(
            url,
            {
                "pageNo": 1,
                "numOfRows": 10,
                "dataType": "JSON",
                "dateTime": date_time,
                "resultType": result_type,
                "dongCode": dong_code,
            },
            key,
        )
        items = self._json_items(payload)
        if not items:
            return None
        item = items[0]
        value = self._optional_float(item.get("value"))
        if value is None:
            return None
        return {
            "date_time": str(item.get("dateTime") or date_time),
            "value": value,
            "unit": item.get("unit"),
            "longitude": self._optional_float(item.get("lon")),
            "latitude": self._optional_float(item.get("lat")),
        }

    @staticmethod
    def _nearby_gk2a_date_times(nominal_time: datetime, *, window_minutes: int = 10) -> list[str]:
        offsets = [0]
        for minute in range(2, max(0, window_minutes) + 1, 2):
            offsets.extend([-minute, minute])
        return [(nominal_time + timedelta(minutes=offset)).strftime("%Y%m%d%H%M") for offset in offsets]

    def _fetch_satellite_sequence(
        self,
        dong_code: str,
        now_kst: datetime,
        key: str,
        *,
        search_hours: int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        warnings: list[str] = []
        records: list[dict[str, Any]] = []
        base = now_kst.replace(minute=0, second=0, microsecond=0)
        for offset in range(max(0, search_hours) + 1):
            nominal_time = base - timedelta(hours=offset)
            nominal_date_time = nominal_time.strftime("%Y%m%d%H%M")
            matched_date_time: str | None = None
            matched_ca: dict[str, Any] | None = None
            matched_cld: dict[str, Any] | None = None
            failed = False

            for candidate_date_time in self._nearby_gk2a_date_times(nominal_time):
                try:
                    ca = self._fetch_gk2a_value(GK2A_CLA_AREA_URL, "ca", candidate_date_time, dong_code, key)
                    time.sleep(0.05)
                    cld = self._fetch_gk2a_value(GK2A_CLD_AREA_URL, "cld", candidate_date_time, dong_code, key)
                    time.sleep(0.05)
                except Exception:
                    failed = True
                    warnings.append(f"gk2a_area_request_failed:{candidate_date_time}")
                    continue
                if ca is not None or cld is not None:
                    matched_date_time = candidate_date_time
                    matched_ca = ca
                    matched_cld = cld
                    break

            if matched_date_time is None:
                if not failed:
                    warnings.append(f"gk2a_area_no_data_near:{nominal_date_time}")
                continue
            if matched_date_time != nominal_date_time:
                warnings.append(f"gk2a_area_nearest_used:{nominal_date_time}->{matched_date_time}")
            records.append(
                {
                    "date_time": nominal_date_time,
                    "source_date_time": matched_date_time,
                    "CA": matched_ca["value"] if matched_ca else None,
                    "CLD": matched_cld["value"] if matched_cld else None,
                    "ca_unit": matched_ca.get("unit") if matched_ca else None,
                    "cld_unit": matched_cld.get("unit") if matched_cld else None,
                }
            )
            if len(records) >= 3:
                break
        if not records:
            warnings.append("gk2a_area_all_missing_proxy_image_filled_missing")
        elif len(records) < 3:
            warnings.append(f"gk2a_area_only_{len(records)}_frames_available_duplicated")
        return sorted(records, key=lambda item: item["date_time"]), warnings

    def _build_proxy_images(
        self,
        records: list[dict[str, Any]],
        weather_values: dict[str, float | None],
    ) -> tuple[np.ndarray, list[dict[str, Any]], list[str]]:
        if not records:
            return np.full((3, 4, 64, 64), MISSING_UINT8, dtype="uint8"), [], []

        sorted_records = sorted(records, key=lambda item: item["date_time"])
        latest = sorted_records[-1]
        latest_dt = datetime.strptime(str(latest["date_time"]), "%Y%m%d%H%M")
        by_stamp = {str(item["date_time"]): item for item in sorted_records}
        frames: list[dict[str, Any]] = []
        proxy_warnings: list[str] = []
        for offset in (2, 1, 0):
            expected = (latest_dt - timedelta(hours=offset)).strftime("%Y%m%d%H%M")
            frame = by_stamp.get(expected)
            if frame is None:
                frame = {**latest, "date_time": expected, "proxy_source_date_time": latest["date_time"]}
                proxy_warnings.append(f"gk2a_area_missing_frame_duplicated_latest:{expected}->{latest['date_time']}")
            frames.append(frame)

        images = np.full((3, 4, 64, 64), MISSING_UINT8, dtype="uint8")
        summary: list[dict[str, Any]] = []
        sky = weather_values.get("SKY")
        sky_cloud_hint = sky is not None and float(sky) >= 3.0

        for index, record in enumerate(frames):
            ca = record.get("CA")
            cld = record.get("CLD")
            ca_encoded = self._encode_cloud_amount(ca, sky_cloud_hint)
            cld_encoded = self._encode_cloud_detection(cld)
            cloud_hint = ca_encoded >= 1 or cld_encoded in {0, 1} or sky_cloud_hint
            cf_encoded = 1 if cloud_hint else 0
            ct_encoded = 3 if cloud_hint else 0

            images[index, 0, :, :] = ca_encoded
            images[index, 1, :, :] = cf_encoded
            images[index, 2, :, :] = ct_encoded
            images[index, 3, :, :] = cld_encoded
            summary.append(
                {
                    "frame_index": index,
                    "date_time": record.get("date_time"),
                    "source_date_time": record.get("source_date_time"),
                    "proxy_source_date_time": record.get("proxy_source_date_time"),
                    "CA": ca,
                    "CLD": cld,
                    "encoded": {
                        "CA": int(ca_encoded),
                        "CF_PROXY": int(cf_encoded),
                        "CT_PROXY": int(ct_encoded),
                        "CLD": int(cld_encoded),
                    },
                }
            )
        return images, summary, proxy_warnings

    @staticmethod
    def _encode_cloud_amount(value: Any, sky_cloud_hint: bool) -> np.uint8:
        parsed = LiveSatellitePredictionService._optional_float(value)
        if parsed is None:
            return np.uint8(1 if sky_cloud_hint else 0)
        if parsed > 1.0:
            return np.uint8(1 if parsed >= 50.0 else 0)
        return np.uint8(1 if parsed >= 1.0 else 0)

    @staticmethod
    def _encode_cloud_detection(value: Any) -> np.uint8:
        parsed = LiveSatellitePredictionService._optional_float(value)
        if parsed is None:
            return np.uint8(255)
        return np.uint8(max(0, min(3, int(round(parsed)))))

    @staticmethod
    def _image_summary(images: np.ndarray) -> dict[str, Any]:
        return {
            "shape": list(images.shape),
            "dtype": str(images.dtype),
            "missing_ratio": float((images == MISSING_UINT8).mean()),
            "channel_means": {
                "CA": float(np.where(images[:, 0] == MISSING_UINT8, np.nan, images[:, 0]).mean()),
                "CF_PROXY": float(np.where(images[:, 1] == MISSING_UINT8, np.nan, images[:, 1]).mean()),
                "CT_PROXY": float(np.where(images[:, 2] == MISSING_UINT8, np.nan, images[:, 2]).mean()),
                "CLD": float(np.where(images[:, 3] == MISSING_UINT8, np.nan, images[:, 3]).mean()),
            },
        }
