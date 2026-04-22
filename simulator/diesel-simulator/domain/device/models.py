from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Enums ---
class DeviceState(str, Enum):
    OFF = "OFF"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    STOPPING = "STOPPING"
    FAULT = "FAULT"
    EMERGENCY_STOP = "EMERGENCY_STOP"

class ControlMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"

# --- Telemetry Components ---
class Instantaneous(BaseModel):
    P: float = 0.0   # kW (유효전력)
    Q: float = 0.0   # kvar (무효전력)
    S: float = 0.0   # kVA (피상전력)
    V: float = 380.0 # V (전압)
    I: float = 0.0   # A (전류)
    f: float = 60.0  # Hz (주파수)
    PF: float = 1.0  # 역률

class Energy(BaseModel):
    kWh: float = 0.0 # 누적 발전량

class FuelSystem(BaseModel):
    level_percent: float = 100.0  # 연료 잔량 (%)
    consumption_rate_lph: float = 0.0 # 시간당 연료 소모량 (L/h)
    remaining_liters: float = 1000.0 # 잔여 연료 (L)

class EngineMetrics(BaseModel):
    rpm: float = 0.0              # 엔진 회전수
    coolant_temp: float = 20.0    # 냉각수 온도 (℃)
    oil_pressure: float = 0.0     # 오일 압력 (bar)

class Status(BaseModel):
    comms_health: str = "ok"

class DieselData(BaseModel):
    instantaneous: Instantaneous = Field(default_factory=Instantaneous)
    energy: Energy = Field(default_factory=Energy)
    fuel: FuelSystem = Field(default_factory=FuelSystem)
    engine: EngineMetrics = Field(default_factory=EngineMetrics)
    status: Status = Field(default_factory=Status)
