from __future__ import annotations

import yaml

from config import TOPOLOGY_PATH
from state import _topology


def load() -> dict:
    if not TOPOLOGY_PATH.exists():
        return {"plant_id": "PLANT-ALPHA", "nodes": [], "lines": []}
    return yaml.safe_load(TOPOLOGY_PATH.read_text(encoding="utf-8")) or {}


def save() -> None:
    with open(TOPOLOGY_PATH, "w", encoding="utf-8") as f:
        yaml.dump(_topology, f, default_flow_style=False, allow_unicode=True)


def find_line(line_id: str) -> dict | None:
    for line in _topology.get("lines", []):
        if line["line_id"] == line_id:
            return line
    return None


def find_switch_line(switch_id: str) -> dict | None:
    for line in _topology.get("lines", []):
        if line.get("switch", {}).get("switch_id") == switch_id:
            return line
    return None
