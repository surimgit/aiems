from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from core.load import LoadFleet, load_fleet_from_config
from core.scenario import ScenarioProfile, load_scenario_profiles


@dataclass(slots=True)
class RuntimeConfig:
    site_id: str
    edge_id: str
    mqtt_broker_host: str
    mqtt_broker_port: int
    publish_interval_sec: float
    fleet: LoadFleet
    scenario_profiles: dict[str, ScenarioProfile]
    devices_path: Path
    scenario_path: Path


# YAML 파일을 읽고 딕셔너리 형태인지 검증한다.
def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return raw


# 디바이스 설정과 시나리오 설정을 묶어 런타임 설정 객체를 만든다.
def load_config(devices_path: Path, scenario_path: Path | None = None) -> RuntimeConfig:
    resolved_devices_path = devices_path.resolve()
    resolved_scenario_path = (
        scenario_path.resolve()
        if scenario_path is not None
        else resolved_devices_path.parent / "scenario.yaml"
    )

    raw_devices = _read_yaml(resolved_devices_path)
    _read_yaml(resolved_scenario_path)

    fleet = load_fleet_from_config(resolved_devices_path)
    profiles = load_scenario_profiles(resolved_scenario_path)

    site_id = str(raw_devices.get("site_id", "")).strip()
    edge_id = str(raw_devices.get("edge_id", "")).strip()
    mqtt_broker_host = str(raw_devices.get("mqtt_broker_host", "localhost")).strip() or "localhost"
    mqtt_broker_port = int(raw_devices.get("mqtt_broker_port", 1883))
    publish_interval_sec = float(raw_devices.get("publish_interval_sec", 1.0))

    if mqtt_broker_port <= 0 or mqtt_broker_port > 65535:
        raise ValueError("mqtt_broker_port must be between 1 and 65535")
    if publish_interval_sec <= 0:
        raise ValueError("publish_interval_sec must be greater than 0")

    return RuntimeConfig(
        site_id=site_id,
        edge_id=edge_id,
        mqtt_broker_host=mqtt_broker_host,
        mqtt_broker_port=mqtt_broker_port,
        publish_interval_sec=publish_interval_sec,
        fleet=fleet,
        scenario_profiles=profiles,
        devices_path=resolved_devices_path,
        scenario_path=resolved_scenario_path,
    )
