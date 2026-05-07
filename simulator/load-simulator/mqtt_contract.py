from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.command_handler import CommandAck
from core.load import LoadDevice


RESOURCE_TYPE = "load"
VALID_MESSAGE_TYPES = frozenset({"telemetry", "event", "emergency", "command", "ack", "heartbeat"})


@dataclass(slots=True)
class TopicParts:
    site_id: str
    resource_type: str
    device_id: str
    message_type: str


@dataclass(slots=True)
class LoadCommandMessage:
    command_id: str
    command_type: str
    payload: dict[str, Any]


# 4세그먼트 MQTT 토픽 문자열을 만든다.
def build_topic(site_id: str, resource_type: str, device_id: str, message_type: str) -> str:
    return f"{site_id}/{resource_type}/{device_id}/{message_type}"


# 사이트 단위 heartbeat 토픽을 만든다.
def build_heartbeat_topic(site_id: str) -> str:
    return f"{site_id}/heartbeat"


# MQTT 토픽을 파싱해 site, device, message 정보를 추출한다.
def parse_topic(topic: str) -> TopicParts:
    parts = topic.split("/")
    if len(parts) != 4:
        raise ValueError(f"Invalid MQTT topic: {topic}")
    site_id, resource_type, device_id, message_type = parts
    if resource_type != RESOURCE_TYPE:
        raise ValueError(f"Unsupported resource type: {resource_type}")
    if message_type not in VALID_MESSAGE_TYPES:
        raise ValueError(f"Unsupported message type: {message_type}")
    return TopicParts(
        site_id=site_id,
        resource_type=resource_type,
        device_id=device_id,
        message_type=message_type,
    )


# load command payload를 파싱하고 필수 필드를 검증한다.
def parse_load_command(topic: str, payload: str, site_id: str) -> tuple[TopicParts, LoadCommandMessage]:
    topic_parts = parse_topic(topic)
    if topic_parts.message_type != "command":
        raise ValueError(f"Unsupported message type: {topic_parts.message_type}")
    if topic_parts.site_id != site_id:
        raise ValueError(f"Command target does not match this simulator: {topic}")

    raw_payload = json.loads(payload)
    if not isinstance(raw_payload, dict):
        raise ValueError("command payload must be a JSON object")

    command_id = str(raw_payload.get("command_id", "")).strip()
    command_type = str(raw_payload.get("command_type", "")).strip()
    command_payload = raw_payload.get("payload", {})

    if not command_id:
        raise ValueError("command_id is required")
    if not command_type:
        raise ValueError("command_type is required")
    if not isinstance(command_payload, dict):
        raise ValueError("payload must be an object")

    return topic_parts, LoadCommandMessage(
        command_id=command_id,
        command_type=command_type,
        payload=command_payload,
    )


# 장치 상태를 MQTT telemetry payload 형식으로 변환한다.
def snapshot_to_telemetry(
    device: LoadDevice,
    *,
    timestamp: datetime | None = None,
    wire_fault: bool = False,
) -> dict[str, Any]:
    observed_at = timestamp or datetime.now(timezone.utc)
    p_kw = 0.0 if wire_fault else device.measurement.p_kw
    i_a = 0.0 if wire_fault else device.measurement.i_a
    comms_health = "wire_fault" if wire_fault else device.state.comms_health
    return {
        "device_id": device.device_id,
        "plant_id": device.site_id,
        "resource_type": RESOURCE_TYPE,
        "timestamp": observed_at.isoformat().replace("+00:00", "Z"),
        "data": {
            "instantaneous": {
                "P": p_kw,
                "Q": device.measurement.q_kvar,
                "V": device.measurement.v_v,
                "I": i_a,
                "f": device.measurement.f_hz,
                "PF": device.measurement.pf,
            },
            "energy": {
                "kWh": device.measurement.kwh,
                "kvarh": device.measurement.kvarh,
                "demand_max": device.measurement.demand_max_kw,
            },
            "status": {
                "comms_health": comms_health,
                "operating_state": device.state.operating_state.value,
                "shed_ratio": device.state.shed_ratio,
                "panel_id": device.panel_id,
            },
        },
    }


# 내부 ACK 객체를 MQTT 응답 payload로 변환한다.
def ack_to_payload(ack: CommandAck) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "command_id": ack.command_id,
        "status": ack.status,
    }
    if ack.reason is not None:
        payload["reason"] = ack.reason
    return payload


# heartbeat 메시지를 MQTT payload 형식으로 생성한다.
def build_heartbeat_message(site_id: str, resource_type: str, device_id: str, *, timestamp: datetime | None = None) -> dict[str, Any]:
    observed_at = timestamp or datetime.now(timezone.utc)
    return {
        "plant_id": site_id,
        "resource_type": resource_type,
        "device_id": device_id,
        "timestamp": observed_at.isoformat().replace("+00:00", "Z"),
        "status": "alive",
    }
