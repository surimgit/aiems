from typing import List, Dict, Optional, Tuple
from datetime import datetime
from .solar import SolarDevice
from .models import EventMessage, TelemetryMessage, CommandAckMessage
from .interpolator import TimeSeriesInterpolator

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, SolarDevice] = {}

    def register_device(self, device: SolarDevice):
        """가상의 하드웨어(시뮬레이터)를 Manager 메모리에 등록합니다."""
        self.devices[device.device_id] = device
        print(f"Registered device: {device.device_id}")

    def get_device(self, device_id: str) -> Optional[SolarDevice]:
        return self.devices.get(device_id)

    def tick_all(self, sim_time: datetime, real_time: datetime) -> Tuple[List[TelemetryMessage], List[EventMessage]]:
        """모든 등록된 기기를 순회하며 현장 상황을 시뮬레이션하고, 결과 데이터를 수집합니다."""
        telemetries = []
        events = []
        
        for device_id, device in self.devices.items():
            event = device.tick(sim_time, real_time)
            if event:
                events.append(event)
            
            telemetries.append(device.get_telemetry(sim_time))
            
        return telemetries, events

    def route_command(self, device_id: str, cmd_payload: dict, current_time: datetime) -> CommandAckMessage:
        """EMS로부터 들어온 명령을 타겟 디바이스에 라우팅합니다."""
        device = self.get_device(device_id)
        if device:
            # 기기가 존재하면 해당 기기에 물리 명령(execute) 수행
            return device.execute_command(cmd_payload, current_time)
        else:
            # 관리하지 않는 기기인 경우 알 수 없음을 반환
            cmd_id = cmd_payload.get("command_id", "unknown")
            return CommandAckMessage(
                command_id=cmd_id,
                status="rejected",
                reason=f"DEVICE_NOT_FOUND: {device_id}"
            )
