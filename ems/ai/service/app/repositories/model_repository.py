from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import settings


@dataclass
class LoadedModel:
    name: str
    model_path: Path
    model: Any
    feature_columns: list[str]
    target_column: str | None


class ModelRepository:
    def __init__(self) -> None:
        self._cache: dict[str, LoadedModel] = {}

    def default_path(self, model_name: str) -> Path:
        if model_name == "solar":
            return Path(settings.default_solar_model_path)
        if model_name == "capacity_factor":
            return Path(settings.default_capacity_factor_model_path)
        raise ValueError(f"Unknown model name: {model_name}")

    def load(self, model_name: str, model_path: str | None = None) -> LoadedModel:
        path = Path(model_path) if model_path else self.default_path(model_name)
        cache_key = f"{model_name}:{path}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        import joblib

        artifact = joblib.load(path)
        model = artifact["model"] if isinstance(artifact, dict) and "model" in artifact else artifact
        feature_columns = artifact.get("feature_columns") if isinstance(artifact, dict) else None
        if not feature_columns:
            raise ValueError(f"feature_columns are missing from model artifact: {path}")

        loaded = LoadedModel(
            name=model_name,
            model_path=path,
            model=model,
            feature_columns=list(feature_columns),
            target_column=artifact.get("target_column") if isinstance(artifact, dict) else None,
        )
        self._cache[cache_key] = loaded
        return loaded

    def status(self) -> list[dict[str, Any]]:
        statuses = []
        for name in ("solar", "capacity_factor"):
            path = self.default_path(name)
            cache_prefix = f"{name}:{path}"
            loaded = self._cache.get(cache_prefix)
            statuses.append(
                {
                    "name": name,
                    "model_path": str(path),
                    "exists": path.exists(),
                    "loaded": loaded is not None,
                    "feature_columns": loaded.feature_columns if loaded else None,
                }
            )
        return statuses

