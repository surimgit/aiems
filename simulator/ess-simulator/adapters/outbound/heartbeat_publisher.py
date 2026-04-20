from __future__ import annotations

from mqtt_contract import build_heartbeat_message, build_heartbeat_topic


def serialize_heartbeat(plant_id: str, resource_type: str, device_id: str) -> str:
    """문서에 정의된 heartbeat 토픽에 실을 최소 생존 신호 JSON을 만든다."""

    return build_heartbeat_message(
        plant_id=plant_id,
        resource_type=resource_type,
        device_id=device_id,
    ).model_dump_json()


def resolve_heartbeat_topic(plant_id: str) -> str:
    """heartbeat는 일반 telemetry와 달리 `{plant_id}/heartbeat` 토픽을 사용한다."""

    return build_heartbeat_topic(plant_id)
