from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT = SERVICE_ROOT.parent
REPO_ROOT = AI_ROOT.parents[1]

for path in (REPO_ROOT, AI_ROOT):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


@dataclass(frozen=True)
class Settings:
    service_name: str = "ai-service"
    api_title: str = "EMS AI Service API"
    api_version: str = "1.0"
    default_solar_model_path: str = os.getenv(
        "S305_SOLAR_MODEL_PATH",
        str(AI_ROOT / "models" / "solar_kpx_lightgbm" / "model.joblib"),
    )
    default_capacity_factor_model_path: str = os.getenv(
        "S305_CAPACITY_FACTOR_MODEL_PATH",
        str(AI_ROOT / "models" / "kpx_5min_capacity_factor_lightgbm" / "model.joblib"),
    )
    default_irradiance_threshold: float = float(os.getenv("S305_IRRADIANCE_THRESHOLD", "10.0"))
    default_max_capacity_factor: float = float(os.getenv("S305_MAX_CAPACITY_FACTOR", "1.0"))
    openai_api_key_env: str = os.getenv("S305_OPENAI_API_KEY_ENV", "OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", os.getenv("S305_OPENAI_MODEL", "gpt-5.4-nano"))
    openai_enabled: bool = os.getenv("S305_OPENAI_ENABLED", "false").lower() == "true"
    load_prior_data_root: str = os.getenv("S305_AI_DATA_ROOT", str(AI_ROOT / "data"))


settings = Settings()
