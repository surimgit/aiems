from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Mapping, TypedDict, cast

from pydantic import BaseModel, Field

from core.command_handler import CommandAck, SimulatorCommand, parse_simulator_command


ResourceType = Literal["solar", "ess", "load"]
MessageType = Literal["telemetry", "event", "emergency", "command", "ack", "heartbeat"]
OperatingMode = Literal["charge", "discharge", "standby"]


class TopicParts(BaseModel):
    """MQTT 토픽을 분해한 결과를 담는다."""

    plant_id: str
    resource_type: ResourceType
    device_id: str
    message_type: MessageType


class EssCommandPayload(BaseModel):
    """ESS 제어 명령 payload를 표현한다."""

    mode: OperatingMode
    target_power_kw: float = Field(ge=0)


class EssCommandMessage(BaseModel):
    """EMS에서 Edge로 보내는 ESS 명령 본문이다."""

    command_id: str
    command_type: Literal["ess_mode"]
    payload: EssCommandPayload


class TelemetryInstantaneousData(BaseModel):
    """순시 전력 계측값 묶음이다."""

    P: float
    Q: float
    V: float
    I: float
    f: float
    PF: float


class TelemetryEnergyData(BaseModel):
    """누적 에너지 계측값 묶음이다."""

    kWh: float
    kvarh: float


class TelemetryStatusData(BaseModel):
    """ESS 상태 필드를 담는다."""

    SOC: float
    operating_mode: OperatingMode
    comms_health: Literal["ok", "error"]


class TelemetryData(BaseModel):
    """Telemetry의 data 블록 전체를 표현한다."""

    instantaneous: TelemetryInstantaneousData
    energy: TelemetryEnergyData
    status: TelemetryStatusData


class TelemetryMessage(BaseModel):
    """Edge가 EMS로 보내는 telemetry envelope이다."""

    device_id: str
    plant_id: str
    resource_type: Literal["ess"]
    timestamp: str
    data: TelemetryData


class AckMessage(BaseModel):
    """명령 처리 결과를 돌려주는 ACK payload이다."""

    command_id: str
    status: Literal["accepted", "rejected"]
    reason: str | None = None


class SimulatorSnapshot(TypedDict):
    """MQTT 직렬화에 필요한 snapshot 최소 필드만 정의한다."""

    device_id: str
    plant_id: str
    resource_type: str
    soc: float
    power_kw: float
    operating_mode: str
    accumulated_energy_kwh: float


def coerce_simulator_snapshot(raw_snapshot: Mapping[str, object]) -> SimulatorSnapshot:
    """시뮬레이터 snapshot을 MQTT 전송용 정형 타입으로 정리한다."""

    return SimulatorSnapshot(
        device_id=_require_str(raw_snapshot["device_id"], "device_id"),
        plant_id=_require_str(raw_snapshot["plant_id"], "plant_id"),
        resource_type=_require_str(raw_snapshot["resource_type"], "resource_type"),
        soc=_require_float(raw_snapshot["soc"], "soc"),
        power_kw=_require_float(raw_snapshot["power_kw"], "power_kw"),
        operating_mode=_require_str(raw_snapshot["operating_mode"], "operating_mode"),
        accumulated_energy_kwh=_require_float(raw_snapshot["accumulated_energy_kwh"], "accumulated_energy_kwh"),
    )


def _require_str(value: object, field_name: str) -> str:
    """문자열 필드를 강제 확인해 타입 오류를 초기에 드러낸다."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    return value


def _require_float(value: object, field_name: str) -> float:
    """숫자 필드를 강제 확인해 잘못된 snapshot 입력을 막는다."""

    if not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def build_topic(plant_id: str, resource_type: str, device_id: str, message_type: str) -> str:
    """문서에서 정한 규격대로 MQTT 토픽 문자열을 만든다."""

    return f"{plant_id}/{resource_type}/{device_id}/{message_type}"


def parse_topic(topic: str) -> TopicParts:
    """4단계 토픽을 파싱하고 규격 위반이면 바로 실패시킨다."""

    parts = topic.split("/")
    if len(parts) != 4:
        raise ValueError(f"Invalid MQTT topic: {topic}")
    if parts[1] not in ("solar", "ess", "load"):
        raise ValueError(f"Unsupported resource type: {parts[1]}")
    if parts[3] not in ("telemetry", "event", "emergency", "command", "ack", "heartbeat"):
        raise ValueError(f"Unsupported message type: {parts[3]}")

    return TopicParts(
        plant_id=parts[0],
        resource_type=cast(ResourceType, parts[1]),
        device_id=parts[2],
        message_type=cast(MessageType, parts[3]),
    )


def parse_ess_command(topic: str, payload: str, plant_id: str, device_id: str) -> tuple[TopicParts, EssCommandMessage]:
    """현재 ESS 장비를 대상으로 한 command인지 검증하고 파싱한다."""

    topic_parts = parse_topic(topic)
    if topic_parts.message_type != "command":
        raise ValueError(f"Unsupported message type: {topic_parts.message_type}")
    if topic_parts.resource_type != "ess":
        raise ValueError(f"Unsupported resource type: {topic_parts.resource_type}")
    if topic_parts.plant_id != plant_id or topic_parts.device_id != device_id:
        raise ValueError(f"Command target does not match this simulator: {topic}")

    return topic_parts, EssCommandMessage.model_validate_json(payload)


def to_ack_message(ack: CommandAck) -> AckMessage:
    """내부 명령 처리 결과를 MQTT ACK 형식으로 변환한다."""

    return AckMessage(
        command_id=ack.command_id,
        status=ack.status,
        reason=ack.reason,
    )


def to_simulator_command(message: EssCommandMessage) -> SimulatorCommand:
    """MQTT 명령 모델을 내부 command handler 입력 모델로 바꾼다."""

    return parse_simulator_command(message.model_dump())


def snapshot_to_telemetry(snapshot: SimulatorSnapshot, *, timestamp: datetime | None = None) -> TelemetryMessage:
    """현재 ESS snapshot을 telemetry payload 형식으로 변환한다."""

    observed_at = timestamp or datetime.now(timezone.utc)
    power_kw = snapshot["power_kw"]
    current_a = 0.0 if power_kw == 0 else abs(power_kw) / 380.0

    return TelemetryMessage(
        device_id=snapshot["device_id"],
        plant_id=snapshot["plant_id"],
        resource_type="ess",
        timestamp=observed_at.isoformat().replace("+00:00", "Z"),
        data=TelemetryData(
            instantaneous=TelemetryInstantaneousData(
                P=power_kw,
                Q=0.0,
                V=380.0,
                I=round(current_a, 3),
                f=60.0,
                PF=1.0,
            ),
            energy=TelemetryEnergyData(
                kWh=snapshot["accumulated_energy_kwh"],
                kvarh=0.0,
            ),
            status=TelemetryStatusData(
                SOC=snapshot["soc"],
                operating_mode=cast(OperatingMode, snapshot["operating_mode"]),
                comms_health="ok",
            ),
        ),
    )
