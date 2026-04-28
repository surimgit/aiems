from __future__ import annotations

import json

import yaml

from config import TOPOLOGY_PATH
from state import _topology

_DEFAULT_TOPOLOGY = {
    "plant_id": "PLANT-ALPHA",
    "nodes": [],
    "lines": [],
}


def load() -> dict:
    if not TOPOLOGY_PATH.exists():
        TOPOLOGY_PATH.parent.mkdir(parents=True, exist_ok=True)
        default = json.loads(json.dumps(_DEFAULT_TOPOLOGY))
        with open(TOPOLOGY_PATH, "w", encoding="utf-8") as f:
            yaml.dump(default, f, default_flow_style=False, allow_unicode=True)
        print(f"[topology] 기본 토폴로지 생성: {TOPOLOGY_PATH}")
        return default
    if TOPOLOGY_PATH.is_dir():
        raise RuntimeError(
            f"TOPOLOGY_PATH({TOPOLOGY_PATH})가 파일이 아닌 디렉토리입니다. "
            "Docker 볼륨 마운트를 확인하세요."
        )
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
