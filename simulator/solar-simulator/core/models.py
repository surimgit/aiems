from enum import Enum
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

# --- Enums ---
class DeviceState(str, Enum):
    IDLE = "IDLE"
    STANDBY = "STANDBY"
    GENERATING = "GENERATING"
    FAULT = "FAULT"
    SAFE_STOP = "SAFE_STOP"
    EMERGENCY_STOP = "EMERGENCY_STOP"

class ControlMode(str, Enum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    EMERGENCY = "EMERGENCY"

# --- Telemetry Components (MQTT Contract 4.1) ---
class Instantaneous(BaseModel):
    P: float = 0.0   # kW
    Q: float = 0.0   # kvar
    S: float = 0.0   # kVA
    V: float = 380.0 # V
    I: float = 0.0   # A
    f: float = 60.0  # Hz
    PF: float = 1.0

class Energy(BaseModel):
    kWh: float = 0.0
    kvarh: float = 0.0

class Status(BaseModel):
    comms_health: str = "ok"

class SolarData(BaseModel):
    instantaneous: Instantaneous = Field(default_factory=Instantaneous)
    energy: Energy = Field(default_factory=Energy)
    status: Status = Field(default_factory=Status)

# --- Message Envelopes (MQTT Contract 3) ---
class TelemetryMessage(BaseModel):
    device_id: str
    plant_id: str
    resource_type: str = "solar"
    timestamp: str # UTC ISO 8601 (e.g. 2026-04-14T07:50:00Z)
    data: SolarData

class EventMessage(BaseModel):
    device_id: str
    plant_id: str
    resource_type: str = "solar"
    timestamp: str
    event_type: str
    severity: str # INFO, WARNING, ALARM, EMERGENCY
    message: str
    data: Optional[Dict[str, Any]] = None

class CommandAckMessage(BaseModel):
    command_id: str
    status: str  # accepted, rejected
    reason: Optional[str] = None
