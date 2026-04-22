from __future__ import annotations

import json

from mqtt_contract import RESOURCE_TYPE, build_heartbeat_message, build_heartbeat_topic


def resolve_heartbeat_topic(site_id: str) -> str:
    return build_heartbeat_topic(site_id)


def serialize_heartbeat(site_id: str, device_id: str) -> str:
    return json.dumps(
        build_heartbeat_message(site_id, RESOURCE_TYPE, device_id),
        separators=(",", ":"),
    )
