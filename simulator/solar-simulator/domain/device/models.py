from enum import Enum
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

# --- Device Data Components ---
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
