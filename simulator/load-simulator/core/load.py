from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Any

import yaml

from core.state_machine import LoadOperatingState, resolve_initial_state, resolve_runtime_state


# 런타임 상태 갱신 시 사용할 UTC 현재 시각을 만든다.
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class LoadDeviceConfig:
    site_id: str
    edge_id: str
    device_id: str
    panel_id: str
    name: str
    rated_kw: float
    base_kw: float
    power_factor: float
    voltage_v: float
    frequency_hz: float
    enabled: bool
    scenario_profile: str

    def __post_init__(self) -> None:
        if not self.site_id.strip():
            raise ValueError("site_id is required")
        if not self.edge_id.strip():
            raise ValueError("edge_id is required")
        if not self.device_id.strip():
            raise ValueError("device_id is required")
        if not self.panel_id.strip():
            raise ValueError("panel_id is required")
        if not self.name.strip():
            raise ValueError("name is required")
        if self.rated_kw <= 0:
            raise ValueError("rated_kw must be greater than 0")
        if self.base_kw < 0:
            raise ValueError("base_kw must be greater than or equal to 0")
        if self.base_kw > self.rated_kw:
            raise ValueError("base_kw must be less than or equal to rated_kw")
        if not 0 < self.power_factor <= 1:
            raise ValueError("power_factor must be between 0 and 1")
        if self.voltage_v <= 0:
            raise ValueError("voltage_v must be greater than 0")
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be greater than 0")
        if not self.scenario_profile.strip():
            raise ValueError("scenario_profile is required")


@dataclass(slots=True)
class LoadMeasurement:
    p_kw: float
    q_kvar: float
    v_v: float
    i_a: float
    f_hz: float
    pf: float
    kwh: float = 0.0
    kvarh: float = 0.0
    demand_max_kw: float = 0.0

    def __post_init__(self) -> None:
        if self.v_v <= 0:
            raise ValueError("v_v must be greater than 0")
        if self.f_hz <= 0:
            raise ValueError("f_hz must be greater than 0")
        if not 0 < self.pf <= 1:
            raise ValueError("pf must be between 0 and 1")
        if self.p_kw < 0:
            raise ValueError("p_kw must be greater than or equal to 0")
        if self.q_kvar < 0:
            raise ValueError("q_kvar must be greater than or equal to 0")
        if self.i_a < 0:
            raise ValueError("i_a must be greater than or equal to 0")
        if self.kwh < 0:
            raise ValueError("kwh must be greater than or equal to 0")
        if self.kvarh < 0:
            raise ValueError("kvarh must be greater than or equal to 0")
        if self.demand_max_kw < 0:
            raise ValueError("demand_max_kw must be greater than or equal to 0")

    @classmethod
    def from_active_power(
        cls,
        *,
        p_kw: float,
        voltage_v: float,
        frequency_hz: float,
        power_factor: float,
        kwh: float = 0.0,
        kvarh: float = 0.0,
        demand_max_kw: float | None = None,
    ) -> "LoadMeasurement":
        q_kvar = p_kw * sqrt(max((1 / (power_factor**2)) - 1, 0.0))
        apparent_power_kva = p_kw / power_factor if power_factor else 0.0
        current_a = (apparent_power_kva * 1000) / (sqrt(3) * voltage_v)
        return cls(
            p_kw=p_kw,
            q_kvar=q_kvar,
            v_v=voltage_v,
            i_a=current_a,
            f_hz=frequency_hz,
            pf=power_factor,
            kwh=kwh,
            kvarh=kvarh,
            demand_max_kw=max(p_kw, demand_max_kw or 0.0),
        )


@dataclass(slots=True)
class LoadState:
    operating_state: LoadOperatingState
    comms_health: str = "ok"
    shed_ratio: float = 0.0
    last_updated_at: datetime = field(default_factory=_utc_now)
    last_command_id: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        if not 0.0 <= self.shed_ratio <= 1.0:
            raise ValueError("shed_ratio must be between 0.0 and 1.0")
        if self.comms_health not in {"ok", "error"}:
            raise ValueError("comms_health must be either 'ok' or 'error'")


@dataclass(slots=True)
class LoadDevice:
    config: LoadDeviceConfig
    measurement: LoadMeasurement
    state: LoadState

    @property
    def site_id(self) -> str:
        return self.config.site_id

    @property
    def edge_id(self) -> str:
        return self.config.edge_id

    @property
    def device_id(self) -> str:
        return self.config.device_id

    @property
    def panel_id(self) -> str:
        return self.config.panel_id

    @classmethod
    def from_config(cls, config: LoadDeviceConfig) -> "LoadDevice":
        measurement = LoadMeasurement.from_active_power(
            p_kw=config.base_kw,
            voltage_v=config.voltage_v,
            frequency_hz=config.frequency_hz,
            power_factor=config.power_factor,
            demand_max_kw=config.base_kw,
        )
        state = LoadState(
            operating_state=resolve_initial_state(config.enabled),
            enabled=config.enabled,
        )
        return cls(config=config, measurement=measurement, state=state)

    # 새 측정값을 장치에 반영하고 상태를 최신화한다.
    def apply_measurement(self, measurement: LoadMeasurement, *, updated_at: datetime | None = None) -> None:
        self.measurement = measurement
        self.state.last_updated_at = updated_at or _utc_now()
        # 정격 110% 초과 시 로컬 과부하 fault 전환
        overload = measurement.p_kw > self.config.rated_kw * 1.1
        self.refresh_operating_state(has_fault=overload)

    # load_shed 결과 비율을 장치 상태에 저장한다.
    def set_shed_ratio(
        self,
        shed_ratio: float,
        *,
        command_id: str | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        if not 0.0 <= shed_ratio <= 1.0:
            raise ValueError("shed_ratio must be between 0.0 and 1.0")
        self.state.shed_ratio = shed_ratio
        self.state.last_command_id = command_id
        self.state.last_updated_at = updated_at or _utc_now()
        self.refresh_operating_state()

    # 현재 측정값과 제어 상태를 기준으로 운전 상태를 다시 계산한다.
    def refresh_operating_state(self, *, has_fault: bool = False) -> LoadOperatingState:
        self.state.operating_state = resolve_runtime_state(
            enabled=self.state.enabled,
            has_fault=has_fault,
            shed_ratio=self.state.shed_ratio,
            has_measurement=self.measurement.p_kw > 0,
        )
        return self.state.operating_state

    # 외부 출력용으로 장치 상태를 딕셔너리 스냅샷으로 만든다.
    def snapshot(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "edge_id": self.edge_id,
            "device_id": self.device_id,
            "panel_id": self.panel_id,
            "name": self.config.name,
            "scenario_profile": self.config.scenario_profile,
            "enabled": self.state.enabled,
            "operating_state": self.state.operating_state.value,
            "comms_health": self.state.comms_health,
            "shed_ratio": self.state.shed_ratio,
            "measurement": {
                "P": self.measurement.p_kw,
                "Q": self.measurement.q_kvar,
                "V": self.measurement.v_v,
                "I": self.measurement.i_a,
                "f": self.measurement.f_hz,
                "PF": self.measurement.pf,
                "kWh": self.measurement.kwh,
                "kvarh": self.measurement.kvarh,
                "demand_max": self.measurement.demand_max_kw,
            },
        }


@dataclass(slots=True)
class LoadFleet:
    site_id: str
    edge_id: str
    _devices: dict[str, LoadDevice] = field(default_factory=dict)
    _panel_index: dict[str, str] = field(default_factory=dict)

    # 장치를 fleet에 등록하면서 중복 식별자를 검증한다.
    def register(self, device: LoadDevice) -> None:
        if device.site_id != self.site_id:
            raise ValueError("device site_id does not match fleet site_id")
        if device.edge_id != self.edge_id:
            raise ValueError("device edge_id does not match fleet edge_id")
        if device.device_id in self._devices:
            raise ValueError(f"duplicate device_id: {device.device_id}")
        if device.panel_id in self._panel_index:
            raise ValueError(f"duplicate panel_id: {device.panel_id}")
        self._devices[device.device_id] = device
        self._panel_index[device.panel_id] = device.device_id

    # device_id로 등록된 장치를 조회한다.
    def get(self, device_id: str) -> LoadDevice | None:
        return self._devices.get(device_id)

    # panel_id를 통해 장치를 조회한다.
    def get_by_panel_id(self, panel_id: str) -> LoadDevice | None:
        device_id = self._panel_index.get(panel_id)
        if device_id is None:
            return None
        return self._devices[device_id]

    # 등록된 모든 장치를 리스트로 반환한다.
    def list_all(self) -> list[LoadDevice]:
        return list(self._devices.values())

    # 활성화된 장치만 골라 반환한다.
    def list_enabled(self) -> list[LoadDevice]:
        return [device for device in self._devices.values() if device.state.enabled]

    # 장치를 fleet에서 제거한다.
    def unregister(self, device_id: str) -> None:
        device = self._devices.pop(device_id, None)
        if device is not None:
            self._panel_index.pop(device.panel_id, None)
            print(f"Unregistered device: {device_id}")

    # 현재 측정 기준 유효전력 합계를 계산한다.
    def total_active_power_kw(self, *, enabled_only: bool = True) -> float:
        devices = self.list_enabled() if enabled_only else self.list_all()
        return sum(device.measurement.p_kw for device in devices)

    # 설정 기준 기본 부하 합계를 계산한다.
    def total_base_power_kw(self, *, enabled_only: bool = True) -> float:
        devices = self.list_enabled() if enabled_only else self.list_all()
        return sum(device.config.base_kw for device in devices)


# YAML 파일을 읽고 딕셔너리 루트인지 확인한다.
def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        loaded = yaml.safe_load(file) or {}
    if not isinstance(loaded, dict):
        raise ValueError("yaml root must be a mapping")
    return loaded


# 장치 설정 파일에서 분전함 설정 목록을 로드한다.
def load_device_configs(path: str | Path) -> list[LoadDeviceConfig]:
    raw = _load_yaml(path)
    site_id = str(raw.get("site_id", "")).strip()
    edge_id = str(raw.get("edge_id", "")).strip()
    loads = raw.get("loads", [])

    if not isinstance(loads, list):
        raise ValueError("loads must be a list")

    seen_device_ids: set[str] = set()
    seen_panel_ids: set[str] = set()
    configs: list[LoadDeviceConfig] = []

    for item in loads:
        if not isinstance(item, dict):
            raise ValueError("each load entry must be a mapping")
        config = LoadDeviceConfig(
            site_id=site_id,
            edge_id=edge_id,
            device_id=str(item.get("device_id", "")).strip(),
            panel_id=str(item.get("panel_id", "")).strip(),
            name=str(item.get("name", "")).strip(),
            rated_kw=float(item.get("rated_kw", 0.0)),
            base_kw=float(item.get("base_kw", 0.0)),
            power_factor=float(item.get("power_factor", 0.0)),
            voltage_v=float(item.get("voltage_v", 0.0)),
            frequency_hz=float(item.get("frequency_hz", 0.0)),
            enabled=bool(item.get("enabled", True)),
            scenario_profile=str(item.get("scenario_profile", "")).strip(),
        )
        if config.device_id in seen_device_ids:
            raise ValueError(f"duplicate device_id: {config.device_id}")
        if config.panel_id in seen_panel_ids:
            raise ValueError(f"duplicate panel_id: {config.panel_id}")
        seen_device_ids.add(config.device_id)
        seen_panel_ids.add(config.panel_id)
        configs.append(config)

    return configs


# 설정 파일에서 fleet 객체를 바로 구성한다.
def load_fleet_from_config(path: str | Path) -> LoadFleet:
    configs = load_device_configs(path)
    if not configs:
        raise ValueError("at least one load device must be defined")

    fleet = LoadFleet(site_id=configs[0].site_id, edge_id=configs[0].edge_id)
    for config in configs:
        fleet.register(LoadDevice.from_config(config))
    return fleet
