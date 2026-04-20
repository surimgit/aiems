import uuid
from datetime import datetime, timedelta
from typing import Optional
from .models import (
    DieselData, Instantaneous, Energy, Status, 
    DeviceState, ControlMode, TelemetryMessage, 
    EventMessage, CommandAckMessage, FuelSystem, EngineMetrics
)

class DieselDevice:
    def __init__(self, plant_id: str, device_id: str, max_capacity_kw: float = 1000.0):
        self.plant_id = plant_id
        self.device_id = device_id
        self.max_capacity_kw = max_capacity_kw

        # State Data
        self.data = DieselData()
        self.state = DeviceState.OFF
        self.mode = ControlMode.AUTO
        
        self.target_p_kw = 0.0 # 목표 출력
        self.fuel_tank_capacity_l = 2000.0
        self.current_fuel_l = 1500.0 # 초기 연료량
        
        self.last_update_time = None
        self.state_start_time = None
        
        # 물리적 특성 상수
        self.STARTUP_TIME_SEC = 10
        self.SHUTDOWN_TIME_SEC = 5
        self.FUEL_CONS_COEFF = 0.25 # 0.25 L per kWh
        self.IDLE_FUEL_LPH = 5.0     # 5 L per hour when idling

    def _format_utc_timestamp(self, dt: datetime) -> str:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    def _update_engine_metrics(self, dt_sec: float):
        """상태에 따른 엔진 물리 지표 업데이트"""
        if self.state == DeviceState.RUNNING:
            # RPM 1800으로 수렴
            self.data.engine.rpm = 1800.0 + (datetime.now().microsecond % 10 - 5) # 미세 진동
            # 온도 상승 (최대 85도)
            self.data.engine.coolant_temp = min(85.0, self.data.engine.coolant_temp + 0.1 * dt_sec)
            self.data.engine.oil_pressure = 4.5 + (datetime.now().microsecond % 4 * 0.1)
        elif self.state == DeviceState.STARTING:
            self.data.engine.rpm = min(1800.0, self.data.engine.rpm + 200.0 * dt_sec)
        elif self.state == DeviceState.STOPPING:
            self.data.engine.rpm = max(0.0, self.data.engine.rpm - 400.0 * dt_sec)
            self.data.engine.coolant_temp = max(40.0, self.data.engine.coolant_temp - 0.05 * dt_sec)
        else:
            self.data.engine.rpm = 0.0
            self.data.engine.oil_pressure = 0.0
            self.data.engine.coolant_temp = max(25.0, self.data.engine.coolant_temp - 0.02 * dt_sec)

    def tick(self, sim_time: datetime, real_time: datetime) -> Optional[EventMessage]:
        if self.last_update_time is None:
            self.last_update_time = real_time
            return None

        dt_sec = (real_time - self.last_update_time).total_seconds()
        self.last_update_time = real_time

        event_msg = None

        # 1. 상태 전이 로직
        if self.state == DeviceState.STARTING:
            if real_time - self.state_start_time >= timedelta(seconds=self.STARTUP_TIME_SEC):
                self.state = DeviceState.RUNNING
                event_msg = EventMessage(
                    device_id=self.device_id, plant_id=self.plant_id,
                    timestamp=self._format_utc_timestamp(real_time),
                    event_type="STATE_CHANGED", severity="INFO",
                    message="발전기가 가동 준비를 마치고 RUNNING 상태가 되었습니다."
                )
        elif self.state == DeviceState.STOPPING:
            if real_time - self.state_start_time >= timedelta(seconds=self.SHUTDOWN_TIME_SEC):
                self.state = DeviceState.OFF
                self.target_p_kw = 0.0

        # 2. 발전량 및 연료 소모 계산
        actual_p = 0.0
        fuel_consumed = 0.0
        
        if self.state == DeviceState.RUNNING:
            actual_p = self.target_p_kw
            # 연료 소모량 = (P * 계수 + 아이들 소모량) * 시간
            fuel_rate = (actual_p * self.FUEL_CONS_COEFF) + self.IDLE_FUEL_LPH
            fuel_consumed = (fuel_rate / 3600.0) * dt_sec
            self.data.fuel.consumption_rate_lph = fuel_rate
        else:
            self.data.fuel.consumption_rate_lph = 0.0

        # 연료 업데이트
        self.current_fuel_l = max(0.0, self.current_fuel_l - fuel_consumed)
        if self.current_fuel_l <= 0 and self.state == DeviceState.RUNNING:
            self.state = DeviceState.FAULT
            event_msg = EventMessage(
                device_id=self.device_id, plant_id=self.plant_id,
                timestamp=self._format_utc_timestamp(real_time),
                event_type="FUEL_EMPTY", severity="EMERGENCY",
                message="연료가 고갈되어 발전기가 정지되었습니다."
            )

        # 3. 데이터 업데이트
        self.data.fuel.remaining_liters = round(self.current_fuel_l, 2)
        self.data.fuel.level_percent = round((self.current_fuel_l / self.fuel_tank_capacity_l) * 100, 1)
        
        self.data.instantaneous.P = actual_p
        self.data.instantaneous.V = 380.0 if self.state == DeviceState.RUNNING else 0.0
        self.data.instantaneous.I = (actual_p * 1000.0) / 380.0 if actual_p > 0 else 0.0
        self.data.energy.kWh += (actual_p / 3600.0) * dt_sec

        self._update_engine_metrics(dt_sec)
        
        return event_msg

    def execute_command(self, cmd: dict, current_time: datetime) -> CommandAckMessage:
        cmd_id = cmd.get("command_id", str(uuid.uuid4()))
        cmd_type = cmd.get("command_type")
        payload = cmd.get("payload", {})
        
        status = "rejected"
        reason = None

        if cmd_type == "start":
            if self.state == DeviceState.OFF:
                self.state = DeviceState.STARTING
                self.state_start_time = current_time
                status = "accepted"
            else:
                reason = f"INVALID_STATE: Currently in {self.state}"
        
        elif cmd_type == "stop":
            if self.state in [DeviceState.RUNNING, DeviceState.STARTING]:
                self.state = DeviceState.STOPPING
                self.state_start_time = current_time
                status = "accepted"
            else:
                reason = f"INVALID_STATE: Currently in {self.state}"

        elif cmd_type == "load_control":
            target_kw = payload.get("target_kw")
            if target_kw is not None:
                if self.state == DeviceState.RUNNING:
                    self.target_p_kw = min(float(target_kw), self.max_capacity_kw)
                    status = "accepted"
                else:
                    reason = "NOT_RUNNING"
            else:
                reason = "MISSING_TARGET_KW"
        else:
            reason = f"UNKNOWN_COMMAND_TYPE: {cmd_type}"
        
        return CommandAckMessage(command_id=cmd_id, status=status, reason=reason)

    def get_telemetry(self, current_time: datetime) -> TelemetryMessage:
        return TelemetryMessage(
            device_id=self.device_id,
            plant_id=self.plant_id,
            timestamp=self._format_utc_timestamp(current_time),
            data=self.data
        )
