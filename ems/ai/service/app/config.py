from __future__ import annotations

from dataclasses import dataclass

from .runtime import AI_ROOT, REPO_ROOT, configure_import_paths, env_bool, env_float, env_str


configure_import_paths()


@dataclass(frozen=True)
class Settings:
    service_name: str = "ai-service"
    api_title: str = "EMS AI Service API"
    api_version: str = "1.0"
    default_solar_model_path: str = env_str(
        "S305_SOLAR_MODEL_PATH",
        str(AI_ROOT / "models" / "solar_kpx_lightgbm" / "model.joblib"),
    )
    default_capacity_factor_model_path: str = env_str(
        "S305_CAPACITY_FACTOR_MODEL_PATH",
        str(AI_ROOT / "models" / "kpx_5min_capacity_factor_lightgbm" / "model.joblib"),
    )
    default_satellite_model_path: str = env_str(
        "S305_SATELLITE_MODEL_PATH",
        str(AI_ROOT / "checkpoints" / "satellite_wind_safe_multihorizon_24h_v10" / "best_model.pt"),
    )
    default_irradiance_threshold: float = env_float("S305_IRRADIANCE_THRESHOLD", 10.0)
    default_max_capacity_factor: float = env_float("S305_MAX_CAPACITY_FACTOR", 1.0)
    openai_api_key_env: str = env_str("S305_OPENAI_API_KEY_ENV", "OPENAI_API_KEY")
    openai_model: str = env_str("OPENAI_MODEL") or env_str("S305_OPENAI_MODEL", "gpt-5.4-nano")
    openai_enabled: bool = env_bool("S305_OPENAI_ENABLED", False)
    load_prior_data_root: str = env_str("S305_AI_DATA_ROOT", str(AI_ROOT / "data"))
    runpod_enabled: bool = env_bool("S305_RUNPOD_ENABLED", True)
    runpod_endpoint_id: str = env_str("S305_RUNPOD_ENDPOINT_ID") or env_str("RUNPOD_ENDPOINT_ID", "2vpedud72bqd09")
    runpod_api_key_env: str = env_str("S305_RUNPOD_API_KEY_ENV", "RUNPOD_KEY")
    runpod_base_url: str = env_str("S305_RUNPOD_BASE_URL", "https://api.runpod.ai/v2")
    runpod_timeout_seconds: float = env_float("S305_RUNPOD_TIMEOUT_SECONDS", 180.0)


settings = Settings()
