from __future__ import annotations

from typing import Any

from ..repositories.model_repository import ModelRepository


class ModelService:
    def __init__(self, repository: ModelRepository | None = None) -> None:
        self.repository = repository or ModelRepository()

    def model_status(self) -> list[dict[str, Any]]:
        return self.repository.status()

