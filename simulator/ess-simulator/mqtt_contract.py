from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Mapping, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field

from core.command_handler import CommandAck, SimulatorCommand, parse_simulator_command


ResourceType = Literal["solar", "ess", "load"]
MessageType = Literal["telemetry", "event", "emergency", "command", "ack", "heartbeat"]
OperatingMode = Literal["charge", "discharge", "standby"]


class ContractModel(BaseModel):
    """문서에 정의되지 않은 필드는 허용하지 않는 MQTT 계약 모델의 공통 부모다."""

    model_config = ConfigDict(extra="forbid")


class TopicParts(ContractModel):
    """일반 MQTT 토픽 4세그먼트를 분해한 결과를 담는다."""

    plant_id: str
    resource_type: ResourceType
    device_id: str
    message_type: MessageType


class HeartbeatTopicParts(ContractModel):
    """heartbeat 전용 2세그먼트 토픽을 표현한다."""

    plant_id: str
    message_type: Literal["heartbeat"]


class EssCommandPayload(ContractModel):
    """브로커가 요구하는 ESS 모드 변경 명령 payload다."""

    mode: OperatingMode
    target_power_kw: float = Field(ge=0)


class EssCommandMessage(ContractModel):
    """EMS가 ESS 시뮬레이터로 보내는 명령 본문 전체다."""

    command_id: str
    command_type: Literal["ess_mode"]
    payload: EssCommandPayload


class TelemetryInstantaneousData(ContractModel):
    """순시 전력 계측값 묶음이다."""

    P: float
    Q: float
    V: float
    I: float
    f: float
    PF: float


class TelemetryEnergyData(ContractModel):
    """누적 에너지 계측값 묶음이다."""

    kWh: float
    kvarh: float


class TelemetryStatusData(ContractModel):
    """ESS 상태 필드 묶음이다."""

    SOC: float
    operating_mode: OperatingMode
    comms_health: Literal["ok", "error"]


class TelemetryData(ContractModel):
    """telemetry payload의 data 블록 전체다."""

    instantaneous: TelemetryInstantaneousData
    energy: TelemetryEnergyData
    status: TelemetryStatusData


class TelemetryMessage(ContractModel):
    """브로커 문서에 정의된 ESS telemetry envelope이다."""

    device_id: str
    plant_id: str
    resource_type: Literal["ess"]
    timestamp: str
    data: TelemetryData


class AckMessage(ContractModel):
    """명령 처리 결과를 브로커 규격으로 직렬화한 ACK 모델이다."""

    command_id: str
    status: Literal["accepted", "rejected"]
    reason: str | None = None


class SimulatorSnapshot(TypedDict):
    """시뮬레이터 내부 상태 중 MQTT 직렬화에 필요한 최소 필드 집합이다."""

    device_id: str
    plant_id: str
    resource_type: str
    soc: float
    power_kw: float
    operating_mode: str
    accumulated_energy_kwh: float


class HeartbeatMessage(ContractModel):
    """heartbeat 토픽은 장비 식별자가 없어서 payload에 최소 식별 정보를 담는다."""

    plant_id: str
    resource_type: Literal["ess"]
    device_id: str
    timestamp: str
    status: Literal["alive"]


def coerce_simulator_snapshot(raw_snapshot: Mapping[str, object]) -> SimulatorSnapshot:
    """내부 snapshot을 telemetry 직렬화에 쓸 정형 구조로 강제 변환한다."""

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
    """snapshot 필드가 문자열이 아니면 계약 위반으로 실패시킨다."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be str")
    return value


def _require_float(value: object, field_name: str) -> float:
    """snapshot 필드가 숫자가 아니면 계약 위반으로 실패시킨다."""

    if not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    return float(value)


def build_topic(plant_id: str, resource_type: str, device_id: str, message_type: str) -> str:
    """문서의 일반 MQTT 토픽 규격으로 4세그먼트 토픽을 만든다."""

    return f"{plant_id}/{resource_type}/{device_id}/{message_type}"


def build_heartbeat_topic(plant_id: str) -> str:
    """문서에 명시된 heartbeat 전용 2세그먼트 토픽을 만든다."""

    return f"{plant_id}/heartbeat"


def parse_topic(topic: str) -> TopicParts:
    """일반 4세그먼트 MQTT 토픽을 검증하고 각 파트를 분리한다."""

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


def parse_heartbeat_topic(topic: str) -> HeartbeatTopicParts:
    """heartbeat 전용 2세그먼트 토픽이 문서 규격과 맞는지 검증한다."""

    parts = topic.split("/")
    if len(parts) != 2 or parts[1] != "heartbeat":
        raise ValueError(f"Invalid heartbeat topic: {topic}")

    return HeartbeatTopicParts(plant_id=parts[0], message_type="heartbeat")


def parse_ess_command(topic: str, payload: str, plant_id: str, device_id: str) -> tuple[TopicParts, EssCommandMessage]:
    """수신한 MQTT 명령이 이 ESS 장비 대상인지 확인하고 계약대로 파싱한다."""

    topic_parts = parse_topic(topic)
    if topic_parts.message_type != "command":
        raise ValueError(f"Unsupported message type: {topic_parts.message_type}")
    if topic_parts.resource_type != "ess":
        raise ValueError(f"Unsupported resource type: {topic_parts.resource_type}")
    if topic_parts.plant_id != plant_id or topic_parts.device_id != device_id:
        raise ValueError(f"Command target does not match this simulator: {topic}")

    return topic_parts, EssCommandMessage.model_validate_json(payload)


def to_ack_message(ack: CommandAck) -> AckMessage:
    """내부 ACK 모델을 브로커로 보낼 MQTT ACK 형태로 바꾼다."""

    return AckMessage(
        command_id=ack.command_id,
        status=ack.status,
        reason=ack.reason,
    )


def to_simulator_command(message: EssCommandMessage) -> SimulatorCommand:
    """MQTT 명령 모델을 내부 command handler 입력 모델로 변환한다."""

    return parse_simulator_command(message.model_dump())


def snapshot_to_telemetry(snapshot: SimulatorSnapshot, *, timestamp: datetime | None = None) -> TelemetryMessage:
    """ESS snapshot을 브로커 문서에 맞는 telemetry payload로 변환한다."""

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


def build_heartbeat_message(
    plant_id: str,
    resource_type: Literal["ess"],
    device_id: str,
    *,
    timestamp: datetime | None = None,
) -> HeartbeatMessage:
    """heartbeat 토픽에 실을 최소 생존 신호 payload를 만든다."""

    observed_at = timestamp or datetime.now(timezone.utc)
    return HeartbeatMessage(
        plant_id=plant_id,
        resource_type=resource_type,
        device_id=device_id,
        timestamp=observed_at.isoformat().replace("+00:00", "Z"),
        status="alive",
    )
