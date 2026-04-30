from typing import Optional, Dict, Any
from pydantic import BaseModel
from domain.device.models import DieselData

# --- Message Envelopes (MQTT Contract) ---
class TelemetryMessage(BaseModel):
    device_id: str
    plant_id: str
    resource_type: str = "diesel"
    timestamp: str # UTC ISO 8601 (e.g. 2026-04-14T07:50:00Z)
    data: DieselData

class EventMessage(BaseModel):
    device_id: str
    plant_id: str
    resource_type: str = "diesel"
    timestamp: str
    event_type: str
    severity: str # INFO, WARNING, ALARM, EMERGENCY
    message: str
    data: Optional[Dict[str, Any]] = None

class CommandAckMessage(BaseModel):
    command_id: str
    status: str  # accepted, rejected
    reason: Optional[str] = None
