from typing import List, Dict, Optional, Tuple
from datetime import datetime
from domain.device.solar_device import SolarDevice
from domain.edge.models import EventMessage, TelemetryMessage, CommandAckMessage
from domain.device.interpolator import TimeSeriesInterpolator

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, SolarDevice] = {}

    def _format_utc_timestamp(self, dt: datetime) -> str:
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def register_device(self, device: SolarDevice):
        """가상의 하드웨어(시뮬레이터)를 Manager 메모리에 등록합니다."""
        self.devices[device.device_id] = device
        print(f"Registered device: {device.device_id}")

    def get_device(self, device_id: str) -> Optional[SolarDevice]:
        return self.devices.get(device_id)

    def notify_comms_alive(self):
        """가입된 모든 기기에 통신 생존 신호를 전달합니다."""
        for device in self.devices.values():
            device.notify_comms_alive()

    def tick_all(self, sim_time: datetime, real_time: datetime) -> Tuple[List[TelemetryMessage], List[EventMessage]]:
        """모든 등록된 기기를 순회하며 현장 상황을 시뮬레이션하고, 결과 데이터를 수집합니다."""
        telemetries = []
        events = []
        
        for device_id, device in self.devices.items():
            event_data = device.tick(sim_time, real_time)
            if event_data:
                # Wrap event
                ev_type, severity, msg, aux_data = event_data
                events.append(EventMessage(
                    device_id=device_id,
                    plant_id=device.plant_id,
                    timestamp=self._format_utc_timestamp(real_time),
                    event_type=ev_type,
                    severity=severity,
                    message=msg,
                    data=aux_data
                ))
            
            # Wrap telemetry
            solar_data = device.get_telemetry(sim_time)
            telemetries.append(TelemetryMessage(
                device_id=device_id,
                plant_id=device.plant_id,
                timestamp=self._format_utc_timestamp(sim_time),
                data=solar_data
            ))
            
        return telemetries, events

    def route_command(self, device_id: str, cmd_payload: dict, current_time: datetime) -> CommandAckMessage:
        """EMS로부터 들어온 명령을 타겟 디바이스에 라우팅합니다."""
        cmd_id = cmd_payload.get("command_id", "unknown")
        
        device = self.get_device(device_id)
        if device:
            # 기기가 존재하면 해당 기기에 물리 명령(execute) 수행
            status, reason = device.execute_command(cmd_payload, current_time)
            return CommandAckMessage(
                command_id=cmd_id,
                status=status,
                reason=reason
            )
        else:
            # 관리하지 않는 기기인 경우 알 수 없음을 반환
            return CommandAckMessage(
                command_id=cmd_id,
                status="rejected",
                reason=f"DEVICE_NOT_FOUND: {device_id}"
            )
