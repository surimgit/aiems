from __future__ import annotations

import os
import sys
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
AI_ROOT = SERVICE_ROOT.parent
REPO_ROOT = AI_ROOT.parents[1]


def configure_import_paths() -> None:
    for path in (REPO_ROOT, AI_ROOT):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip('"').strip("'")
    return cleaned or None


def env_str(name: str, default: str | None = None) -> str | None:
    return clean_env_value(os.getenv(name)) or default


def env_bool(name: str, default: bool = False) -> bool:
    value = env_str(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "y", "on"}


def env_float(name: str, default: float) -> float:
    value = env_str(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default
