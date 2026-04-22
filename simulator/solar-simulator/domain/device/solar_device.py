import uuid
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from domain.device.models import (
    SolarData, Instantaneous, Energy, Status, 
    DeviceState, ControlMode
)
from domain.device.interpolator import TimeSeriesInterpolator

class SolarDevice:
    def __init__(self, plant_id: str, device_id: str, interpolator: TimeSeriesInterpolator):
        self.plant_id = plant_id
        self.device_id = device_id
        self.interpolator = interpolator

        # State Data
        self.data = SolarData()
        self.reported_state = DeviceState.STANDBY
        self.mode = ControlMode.AUTO
        
        self.emergency_stop = False
        self.local_fault = False
        
        # Curtailment (명세서 5.2)
        self.curtailment_limit_kw = float('inf')

        self.last_update_time = None
        self.max_current_a = 10000.0

    def tick(self, sim_time: datetime, real_time: datetime) -> Optional[Tuple[str, str, str, Dict[str, Any]]]:
        # 발전량 계산 (W -> kW)
        raw_p = self.interpolator.get_interpolated_value(sim_time) / 1000.0
        
        # 출력 제한 적용 (Curtailment)
        actual_p = min(raw_p, self.curtailment_limit_kw)

        if self.mode == ControlMode.AUTO and not self.local_fault and not self.emergency_stop:
            if actual_p > 0:
                self.reported_state = DeviceState.GENERATING
            else:
                self.reported_state = DeviceState.STANDBY

        if self.reported_state != DeviceState.GENERATING:
            actual_p = 0.0

        v_val = 380.0
        i_val = (actual_p * 1000.0) / v_val if actual_p > 0 else 0.0

        event_data = None
        if not self.local_fault and not self.emergency_stop:
            if i_val > self.max_current_a:
                self.local_fault = True
                self.reported_state = DeviceState.FAULT
                event_data = (
                    "OVER_CURRENT",
                    "EMERGENCY",
                    f"과전류({i_val:.2f}A) 발생으로 차단되었습니다.",
                    {"current_a": i_val, "threshold_a": self.max_current_a}
                )
                actual_p = 0.0
                i_val = 0.0

        # Update Energy & Data
        if self.last_update_time:
            hours_diff = (real_time - self.last_update_time).total_seconds() / 3600.0
            self.data.energy.kWh += actual_p * hours_diff

        self.last_update_time = real_time
        self.data.instantaneous.P = round(actual_p, 2)
        self.data.instantaneous.V = v_val
        self.data.instantaneous.I = round(i_val, 3)
        self.data.instantaneous.S = round(actual_p, 2)
        
        return event_data

    def execute_command(self, cmd: dict, current_time: datetime) -> Tuple[str, Optional[str]]:
        cmd_type = cmd.get("command_type")
        payload = cmd.get("payload", {})
        
        result = "rejected"
        reason = None

        if cmd_type == "curtailment":
            limit = payload.get("limit_kw")
            if limit is not None:
                self.curtailment_limit_kw = float(limit)
                result = "accepted"
            else:
                reason = "MISSING_LIMIT_KW"
        
        # 공통 명령어 처리 (필요시)
        elif cmd_type == "mode_change":
            action = payload.get("action")
            if action == "RESET":
                self.local_fault = False
                self.emergency_stop = False
                self.curtailment_limit_kw = float('inf')
                self.reported_state = DeviceState.STANDBY
                result = "accepted"
        else:
            reason = f"UNKNOWN_COMMAND_TYPE: {cmd_type}"

        return result, reason

    def get_telemetry(self, current_time: datetime) -> SolarData:
        return self.data
