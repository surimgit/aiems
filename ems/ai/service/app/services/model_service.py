from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import settings
from ..repositories.model_repository import ModelRepository

try:
    from ems.ai.inference.satellite_wind_safe import DEFAULT_NUM_COLS
except ImportError:
    from inference.satellite_wind_safe import DEFAULT_NUM_COLS


class ModelService:
    def __init__(self, repository: ModelRepository | None = None) -> None:
        self.repository = repository or ModelRepository()

    def model_status(self) -> list[dict[str, Any]]:
        statuses = self.repository.status()
        satellite_path = Path(settings.default_satellite_model_path)
        statuses.append(
            {
                "name": "satellite_wind_safe",
                "model_path": str(satellite_path),
                "exists": satellite_path.exists(),
                "loaded": False,
                "feature_columns": DEFAULT_NUM_COLS,
            }
        )
        return statuses
