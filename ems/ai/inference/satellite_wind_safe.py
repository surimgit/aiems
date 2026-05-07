from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


MODEL_NAME = "satellite_wind_safe_v6"

BASE_NUM_COLS = [
    "cap_scaled",
    "solar_elev_scaled",
    "is_daylight",
    "hour_scaled",
    "doy_scaled",
    "month_scaled",
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_year_sin",
    "day_of_year_cos",
]

WIND_SAFE_COLS = [
    "wind_u_scaled",
    "wind_v_scaled",
    "wind_speed_scaled",
    "wind_dir_sin",
    "wind_dir_cos",
    "asos_ta_scaled",
    "asos_hm_scaled",
    "asos_rn_log1p",
]

DEFAULT_NUM_COLS = BASE_NUM_COLS + WIND_SAFE_COLS
DEFAULT_REGION_MAP = {"대전시": 0, "부산시": 1, "서울시": 2, "울산시": 3, "제주도": 4}
DEFAULT_HORIZON_MAP = {1: 0, 2: 1, 3: 2, 6: 3}


class SatelliteInferenceError(ValueError):
    pass


@dataclass(frozen=True)
class SatelliteModelMetadata:
    model_path: Path
    num_cols: list[str]
    region_map: dict[str, int]
    horizon_map: dict[int, int]
    image_normalization: str
    device: str


def _first_present(source: dict[str, Any], names: tuple[str, ...], default: Any = None) -> Any:
    for name in names:
        if name in source and source[name] is not None:
            return source[name]
    return default


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip()
        if not text or text in {"강수없음", "없음", "-"}:
            return default
        text = text.replace("mm", "").strip()
        if text.startswith("1mm 미만"):
            return 0.5
        value = text
    try:
        if np.isnan(value):
            return default
    except TypeError:
        pass
    return float(value)


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None:
        raise SatelliteInferenceError("target_time or target_timestamp_kst is required")
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise SatelliteInferenceError(f"Invalid target_time: {value}") from exc


def _time_features(source: dict[str, Any]) -> dict[str, float]:
    timestamp_value = _first_present(source, ("target_time", "target_timestamp_kst", "timestamp_kst"))
    timestamp = _parse_time(timestamp_value)
    hour = int(_first_present(source, ("hour",), timestamp.hour))
    day_of_year = int(_first_present(source, ("day_of_year", "doy"), timestamp.timetuple().tm_yday))
    month = int(_first_present(source, ("month",), timestamp.month))
    hour_rad = 2.0 * math.pi * hour / 24.0
    doy_rad = 2.0 * math.pi * day_of_year / 366.0
    return {
        "hour_scaled": hour / 23.0,
        "doy_scaled": day_of_year / 366.0,
        "month_scaled": month / 12.0,
        "hour_of_day_sin": math.sin(hour_rad),
        "hour_of_day_cos": math.cos(hour_rad),
        "day_of_year_sin": math.sin(doy_rad),
        "day_of_year_cos": math.cos(doy_rad),
    }


def _derived_num_features(source: dict[str, Any], payload: dict[str, Any]) -> dict[str, float]:
    values = _time_features(source)

    capacity_kw = _first_present(
        source,
        ("model_capacity_kw", "estimated_capacity_kw", "installed_capacity_kw"),
        _first_present(payload, ("model_capacity_kw", "estimated_capacity_kw", "installed_capacity_kw"), 0.0),
    )
    solar_elevation = _float(
        _first_present(source, ("solar_elevation", "solar_elevation_deg", "solar_elevation_mid"), 0.0)
    )
    is_daylight = _first_present(source, ("is_daylight", "daylight_flag"), None)
    if is_daylight is None:
        is_daylight = 1.0 if solar_elevation > 0.0 else 0.0

    wind_speed = _float(_first_present(source, ("wind_speed_ms", "WSD", "wsd"), 0.0))
    wind_dir = _float(_first_present(source, ("wind_dir_deg", "wind_direction_deg", "VEC", "vec"), 0.0))
    wind_dir = wind_dir % 360.0
    wind_rad = math.radians(wind_dir)
    wind_dir_sin = math.sin(wind_rad) if wind_speed > 0 else 0.0
    wind_dir_cos = math.cos(wind_rad) if wind_speed > 0 else 0.0
    wind_u = wind_speed * wind_dir_sin
    wind_v = wind_speed * wind_dir_cos

    temperature_c = _float(_first_present(source, ("asos_ta", "temperature_c", "TMP", "T1H"), 15.0))
    humidity_pct = _float(_first_present(source, ("asos_hm", "humidity_pct", "REH"), 60.0))
    rainfall_mm = _float(_first_present(source, ("asos_rn", "rainfall_mm", "RN1", "PCP"), 0.0))

    values.update(
        {
            "cap_scaled": _float(capacity_kw) / 300000.0,
            "solar_elev_scaled": solar_elevation / 90.0,
            "is_daylight": float(is_daylight),
            "wind_u_scaled": wind_u / 15.0,
            "wind_v_scaled": wind_v / 15.0,
            "wind_speed_scaled": wind_speed / 15.0,
            "wind_dir_sin": wind_dir_sin,
            "wind_dir_cos": wind_dir_cos,
            "asos_ta_scaled": (temperature_c + 30.0) / 70.0,
            "asos_hm_scaled": humidity_pct / 100.0,
            "asos_rn_log1p": math.log1p(max(0.0, rainfall_mm)),
        }
    )
    return values


def build_num_vector(source: dict[str, Any], payload: dict[str, Any], num_cols: list[str]) -> np.ndarray:
    if all(column in source for column in num_cols):
        values = [_float(source[column]) for column in num_cols]
    else:
        derived = _derived_num_features(source, payload)
        missing = [column for column in num_cols if column not in derived]
        if missing:
            raise SatelliteInferenceError(f"Missing satellite numeric feature columns: {missing}")
        values = [derived[column] for column in num_cols]
    return np.asarray(values, dtype=np.float32)


def _normalize_image(images: np.ndarray, mode: str) -> np.ndarray:
    image = np.asarray(images, dtype=np.float32).copy()
    if image.shape == (12, 64, 64):
        image = image.reshape(3, 4, 64, 64)
    if image.shape != (3, 4, 64, 64):
        raise SatelliteInferenceError(f"images must have shape (3, 4, 64, 64) or (12, 64, 64), got {image.shape}")

    image[image == 255.0] = 0.0
    if mode == "legacy_percent":
        image[:, 0] = image[:, 0] / 100.0
        image[:, 1] = image[:, 1] / 100.0
    elif mode == "binary":
        image[:, 0] = image[:, 0].clip(0.0, 1.0)
        image[:, 1] = image[:, 1].clip(0.0, 1.0)
    else:
        raise SatelliteInferenceError(f"Unknown image normalization mode: {mode}")

    image[:, 2] = image[:, 2] / 9.0
    image[:, 3] = image[:, 3] / 3.0
    return image.reshape(12, 64, 64).astype(np.float32)


def _load_image(source: dict[str, Any], image_normalization: str) -> np.ndarray:
    if "images" in source:
        return _normalize_image(np.asarray(source["images"]), image_normalization)

    image_path = _first_present(source, ("image_npz_path", "image_path"))
    if image_path is None:
        raise SatelliteInferenceError("Each feature must include images or image_npz_path/image_path")

    path = Path(str(image_path))
    if not path.exists():
        raise FileNotFoundError(f"Satellite image file not found: {path}")
    image_row = int(_first_present(source, ("image_row", "sequence_index"), 0))
    with np.load(path) as archive:
        images = archive["images"][image_row]
    return _normalize_image(images, image_normalization)


def _load_checkpoint(path: Path, device: str) -> dict[str, Any]:
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch is required for satellite model inference") from exc

    try:
        checkpoint = torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        checkpoint = torch.load(path, map_location=device)
    if not isinstance(checkpoint, dict):
        raise SatelliteInferenceError(f"Unsupported satellite checkpoint format: {path}")
    return checkpoint


def _state_dict(checkpoint: dict[str, Any]) -> dict[str, Any]:
    state = checkpoint.get("model_state", checkpoint)
    if not isinstance(state, dict):
        raise SatelliteInferenceError("Satellite checkpoint does not contain a model state dict")
    if any(str(key).startswith("module.") for key in state):
        return {str(key).removeprefix("module."): value for key, value in state.items()}
    return state


def _build_model_from_state(state: dict[str, Any], num_dim: int):
    import torch
    import torch.nn as nn

    conv1 = state["image.0.weight"]
    conv2 = state["image.4.weight"]
    conv3 = state["image.8.weight"]
    region_weight = state["region.weight"]
    horizon_weight = state["horizon.weight"]
    tab0 = state["tab.0.weight"]
    tab2 = state["tab.2.weight"]
    head0 = state["head.0.weight"]

    image_channels = int(conv1.shape[1])
    image_widths = (int(conv1.shape[0]), int(conv2.shape[0]), int(conv3.shape[0]))
    n_regions, region_dim = int(region_weight.shape[0]), int(region_weight.shape[1])
    n_horizons, horizon_dim = int(horizon_weight.shape[0]), int(horizon_weight.shape[1])
    tab_hidden = (int(tab0.shape[0]), int(tab2.shape[0]))
    inferred_num_dim = int(tab0.shape[1]) - region_dim - horizon_dim
    head_hidden = int(head0.shape[0])

    if inferred_num_dim != num_dim:
        raise SatelliteInferenceError(
            f"Checkpoint expects {inferred_num_dim} numeric features, but {num_dim} columns were configured"
        )

    class SatelliteSolarModel(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            c1, c2, c3 = image_widths
            self.image = nn.Sequential(
                nn.Conv2d(image_channels, c1, 3, padding=1),
                nn.BatchNorm2d(c1),
                nn.SiLU(),
                nn.MaxPool2d(2),
                nn.Conv2d(c1, c2, 3, padding=1),
                nn.BatchNorm2d(c2),
                nn.SiLU(),
                nn.MaxPool2d(2),
                nn.Conv2d(c2, c3, 3, padding=1),
                nn.BatchNorm2d(c3),
                nn.SiLU(),
                nn.AdaptiveAvgPool2d(1),
            )
            self.region = nn.Embedding(n_regions, region_dim)
            self.horizon = nn.Embedding(n_horizons, horizon_dim)
            self.tab = nn.Sequential(
                nn.Linear(num_dim + region_dim + horizon_dim, tab_hidden[0]),
                nn.SiLU(),
                nn.Linear(tab_hidden[0], tab_hidden[1]),
                nn.SiLU(),
            )
            self.head = nn.Sequential(
                nn.Linear(c3 + tab_hidden[1], head_hidden),
                nn.SiLU(),
                nn.Dropout(0.1),
                nn.Linear(head_hidden, 1),
            )

        def forward(self, image, num, region, horizon):
            image_feat = self.image(image).flatten(1)
            tab_input = torch.cat([num, self.region(region), self.horizon(horizon)], dim=1)
            tab_feat = self.tab(tab_input)
            return self.head(torch.cat([image_feat, tab_feat], dim=1)).squeeze(1)

    model = SatelliteSolarModel()
    model.load_state_dict(state)
    return model


class SatelliteWindSafePredictor:
    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str | None = None,
        image_normalization: str | None = None,
    ) -> None:
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("PyTorch is required for satellite model inference") from exc

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Satellite model file not found: {path}")

        resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        checkpoint = _load_checkpoint(path, resolved_device)
        state = _state_dict(checkpoint)

        num_cols = checkpoint.get("num_cols") or checkpoint.get("tab_cols") or DEFAULT_NUM_COLS
        num_cols = [str(column) for column in num_cols]
        model = _build_model_from_state(state, len(num_cols)).to(resolved_device)
        model.eval()

        region_map = checkpoint.get("region_map") or DEFAULT_REGION_MAP
        horizon_map = checkpoint.get("horizon_map") or DEFAULT_HORIZON_MAP
        config = checkpoint.get("config") if isinstance(checkpoint.get("config"), dict) else {}
        normalization = (
            image_normalization
            or os.getenv("S305_SATELLITE_IMAGE_NORMALIZATION")
            or config.get("image_normalization")
            or "binary"
        )

        self._torch = torch
        self.model = model
        self.metadata = SatelliteModelMetadata(
            model_path=path,
            num_cols=num_cols,
            region_map={str(key): int(value) for key, value in region_map.items()},
            horizon_map={int(key): int(value) for key, value in horizon_map.items()},
            image_normalization=str(normalization),
            device=resolved_device,
        )

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            raise SatelliteInferenceError("features must be a non-empty list")

        images: list[np.ndarray] = []
        nums: list[np.ndarray] = []
        regions: list[int] = []
        horizons: list[int] = []

        for source in features:
            if not isinstance(source, dict):
                raise SatelliteInferenceError("Each feature must be an object")

            region_name = str(_first_present(source, ("region",), payload.get("region", "")))
            if region_name not in self.metadata.region_map:
                raise SatelliteInferenceError(f"Unknown region for satellite model: {region_name}")

            horizon_hours = int(_float(_first_present(source, ("horizon_hours",), payload.get("horizon_hours", 1)), 1))
            if horizon_hours not in self.metadata.horizon_map:
                raise SatelliteInferenceError(
                    f"Unsupported horizon_hours for satellite model: {horizon_hours}. "
                    f"Supported: {sorted(self.metadata.horizon_map)}"
                )

            images.append(_load_image(source, self.metadata.image_normalization))
            nums.append(build_num_vector(source, payload, self.metadata.num_cols))
            regions.append(self.metadata.region_map[region_name])
            horizons.append(self.metadata.horizon_map[horizon_hours])

        torch = self._torch
        with torch.no_grad():
            image_tensor = torch.from_numpy(np.stack(images)).to(self.metadata.device)
            num_tensor = torch.from_numpy(np.stack(nums)).to(self.metadata.device)
            region_tensor = torch.tensor(regions, dtype=torch.long, device=self.metadata.device)
            horizon_tensor = torch.tensor(horizons, dtype=torch.long, device=self.metadata.device)
            raw = self.model(image_tensor, num_tensor, region_tensor, horizon_tensor).detach().cpu().numpy()

        max_capacity_factor = float(payload.get("max_capacity_factor") or 1.0)
        clipped = np.clip(raw, 0.0, max_capacity_factor)

        predictions: list[dict[str, Any]] = []
        for index, source in enumerate(features):
            raw_prediction = float(raw[index])
            predicted_capacity_factor = float(clipped[index])
            reasons: list[str] = []

            solar_elevation = _float(
                _first_present(source, ("solar_elevation", "solar_elevation_deg", "solar_elevation_mid"), 0.0)
            )
            is_daylight = _first_present(source, ("is_daylight", "daylight_flag"), None)
            if (is_daylight is not None and _float(is_daylight) <= 0.0) or (
                is_daylight is None and solar_elevation <= 0.0
            ):
                predicted_capacity_factor = 0.0
                reasons.append("night_zero_clamp")
            elif raw_prediction < 0.0:
                reasons.append("negative_clamp")
            elif predicted_capacity_factor != raw_prediction:
                reasons.append("capacity_factor_clamp")

            installed_capacity_kw = _float(
                _first_present(
                    source,
                    ("installed_capacity_kw",),
                    _first_present(payload, ("installed_capacity_kw",), None),
                ),
                default=float("nan"),
            )
            if math.isnan(installed_capacity_kw):
                raise SatelliteInferenceError("installed_capacity_kw is required for satellite prediction")

            predictions.append(
                {
                    "target_time": _first_present(source, ("target_time", "target_timestamp_kst"), None),
                    "region": _first_present(source, ("region",), payload.get("region")),
                    "site_id": _first_present(source, ("site_id",), payload.get("site_id")),
                    "horizon_hours": int(_first_present(source, ("horizon_hours",), payload.get("horizon_hours", 1))),
                    "raw_predicted_capacity_factor": raw_prediction,
                    "predicted_capacity_factor": predicted_capacity_factor,
                    "installed_capacity_kw": installed_capacity_kw,
                    "predicted_generation_kw": predicted_capacity_factor * installed_capacity_kw,
                    "postprocess_reason": ",".join(reasons) if reasons else "none",
                    "confidence": 0.95 if "night_zero_clamp" in reasons else 0.75,
                    "fallback_flag": False,
                    "model_version": payload.get("model_version") or MODEL_NAME,
                }
            )

        return {
            "ok": True,
            "task": "predict_satellite_capacity_factor",
            "model_path": str(self.metadata.model_path),
            "rows": len(predictions),
            "structured_profile": payload.get("structured_profile"),
            "context_features": payload.get("context_features"),
            "metadata": {
                "num_cols": self.metadata.num_cols,
                "region_map": self.metadata.region_map,
                "horizon_map": self.metadata.horizon_map,
                "image_normalization": self.metadata.image_normalization,
                "device": self.metadata.device,
            },
            "predictions": predictions,
        }


_PREDICTOR_CACHE: dict[tuple[str, str | None, str | None], SatelliteWindSafePredictor] = {}


def predict_satellite_capacity_factor(
    payload: dict[str, Any],
    *,
    model_path: str | Path,
    device: str | None = None,
    image_normalization: str | None = None,
) -> dict[str, Any]:
    cache_key = (str(Path(model_path)), device, image_normalization)
    predictor = _PREDICTOR_CACHE.get(cache_key)
    if predictor is None:
        predictor = SatelliteWindSafePredictor(
            model_path,
            device=device,
            image_normalization=image_normalization,
        )
        _PREDICTOR_CACHE[cache_key] = predictor
    return predictor.predict(payload)
