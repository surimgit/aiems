from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..config import settings
from ..domain.capacity_factor import capacity_kw, is_night_for_capacity_factor
from ..repositories.model_repository import ModelRepository

try:
    from train.solar_postprocess import postprocess_solar_predictions
except ImportError:
    from ems.ai.train.solar_postprocess import postprocess_solar_predictions


class PredictionService:
    def __init__(self, repository: ModelRepository | None = None) -> None:
        self.repository = repository or ModelRepository()

    def predict_solar(self, payload: dict[str, Any]) -> dict[str, Any]:
        loaded = self.repository.load("solar", payload.get("model_path"))
        features = payload["features"]
        frame = self._feature_frame(features, loaded.feature_columns)

        raw_predictions = loaded.model.predict(frame[loaded.feature_columns])
        postprocessed = postprocess_solar_predictions(
            frame,
            raw_predictions,
            installed_capacity_kw=payload.get("installed_capacity_kw"),
            irradiance_threshold=float(payload.get("irradiance_threshold") or settings.default_irradiance_threshold),
        )

        predictions = []
        for index, row in postprocessed.iterrows():
            source = features[index]
            reason = row["postprocess_reason"]
            predictions.append(
                {
                    "target_time": source.get("target_time"),
                    "site_id": source.get("site_id", payload.get("site_id")),
                    "raw_predicted_solar_kw": float(row["raw_predicted_solar_kw"]),
                    "predicted_solar_kw": float(row["predicted_solar_kw"]),
                    "postprocess_reason": reason,
                    "confidence": 0.95 if reason == "night_zero_clamp" else 0.8,
                    "fallback_flag": False,
                    "model_version": payload.get("model_version") or loaded.model_path.parent.name,
                }
            )

        return {
            "ok": True,
            "task": "predict_solar",
            "model_path": str(loaded.model_path),
            "rows": len(predictions),
            "predictions": predictions,
        }

    def predict_capacity_factor(self, payload: dict[str, Any]) -> dict[str, Any]:
        loaded = self.repository.load("capacity_factor", payload.get("model_path"))
        features = payload["features"]
        frame = self._feature_frame(features, loaded.feature_columns)

        raw_predictions = loaded.model.predict(frame[loaded.feature_columns])
        max_capacity_factor = float(payload.get("max_capacity_factor") or settings.default_max_capacity_factor)
        clipped_predictions = np.clip(raw_predictions, 0.0, max_capacity_factor)

        predictions = []
        for index, raw_prediction in enumerate(raw_predictions):
            source = features[index]
            predicted_capacity_factor = float(clipped_predictions[index])
            reasons: list[str] = []

            if is_night_for_capacity_factor(source):
                predicted_capacity_factor = 0.0
                reasons.append("night_zero_clamp")
            elif raw_prediction < 0.0:
                reasons.append("negative_clamp")
            elif predicted_capacity_factor != float(raw_prediction):
                reasons.append("capacity_factor_clamp")

            installed_capacity_kw = capacity_kw(payload, source)
            predictions.append(
                {
                    "target_time": source.get("target_time"),
                    "region": source.get("region", payload.get("region")),
                    "site_id": source.get("site_id", payload.get("site_id")),
                    "raw_predicted_capacity_factor": float(raw_prediction),
                    "predicted_capacity_factor": predicted_capacity_factor,
                    "installed_capacity_kw": installed_capacity_kw,
                    "predicted_generation_kw": predicted_capacity_factor * installed_capacity_kw,
                    "postprocess_reason": ",".join(reasons) if reasons else "none",
                    "confidence": 0.95 if "night_zero_clamp" in reasons else 0.8,
                    "fallback_flag": False,
                    "model_version": payload.get("model_version") or loaded.model_path.parent.name,
                }
            )

        return {
            "ok": True,
            "task": "predict_capacity_factor",
            "model_path": str(loaded.model_path),
            "rows": len(predictions),
            "structured_profile": payload.get("structured_profile"),
            "context_features": payload.get("context_features"),
            "predictions": predictions,
        }

    @staticmethod
    def _feature_frame(features: list[dict[str, Any]], feature_columns: list[str]) -> pd.DataFrame:
        if not features:
            raise ValueError("features must not be empty")
        frame = pd.DataFrame(features)
        missing = [column for column in feature_columns if column not in frame.columns]
        if missing:
            raise ValueError(f"Missing feature columns for prediction: {missing}")
        return frame

