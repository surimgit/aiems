from __future__ import annotations

import os
from pathlib import Path

import yaml


def expand_paths(value):
    if isinstance(value, dict):
        return {key: expand_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_paths(item) for item in value]
    if isinstance(value, str):
        return os.path.expanduser(os.path.expandvars(value))
    return value


def load_config(path: str | Path) -> dict:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        return expand_paths(yaml.safe_load(file))
