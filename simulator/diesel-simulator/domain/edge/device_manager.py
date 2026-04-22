from typing import List, Dict, Optional, Tuple
from datetime import datetime
from domain.device.diesel_device import DieselDevice
from domain.edge.models import EventMessage, TelemetryMessage, CommandAckMessage

class DeviceManager:
    def __init__(self):
        self.devices: Dict[str, DieselDevice] = {}

    def _format_utc_timestamp(self, dt: datetime) -> str:
        return dt.isoformat(timespec='milliseconds').replace('+00:00', 'Z')

    def register_device(self, device: DieselDevice):
        """가상의 하드웨어(시뮬레이터)를 Manager 메모리에 등록합니다."""
        self.devices[device.device_id] = device
        print(f"Registered device: {device.device_id}")

    def get_device(self, device_id: str) -> Optional[DieselDevice]:
        return self.devices.get(device_id)

    def tick_all(self, real_time: datetime) -> Tuple[List[TelemetryMessage], List[EventMessage]]:
        """모든 등록된 기기를 순회하며 현장 상황을 시뮬레이션하고, 결과 데이터를 수집합니다."""
        telemetries = []
        events = []
        
        for device_id, device in self.devices.items():
            event_data = device.tick(real_time, real_time)
            if event_data:
                # Wrap event — device.tick()은 (event_type, severity, message, data) 튜플 반환
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
            diesel_data = device.get_telemetry(real_time)
            telemetries.append(TelemetryMessage(
                device_id=device_id,
                plant_id=device.plant_id,
                timestamp=self._format_utc_timestamp(real_time),
                data=diesel_data
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
            # 관리하지 않는 기기인 경우
            return CommandAckMessage(
                command_id=cmd_id,
                status="rejected",
                reason=f"DEVICE_NOT_FOUND: {device_id}"
            )
