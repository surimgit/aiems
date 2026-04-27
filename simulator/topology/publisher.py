from __future__ import annotations

import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from state import _topology

_mqtt_client: mqtt.Client | None = None


def set_client(client: mqtt.Client) -> None:
    global _mqtt_client
    _mqtt_client = client


def publish(topic: str, payload: dict, *, retain: bool = True) -> None:
    if _mqtt_client is None:
        return
    try:
        _mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False), retain=retain)
    except Exception as e:
        print(f"[topology] publish error: {e}")


def publish_event(event: str, extra: dict) -> None:
    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    topic = f"{plant_id}/topology/event"
    payload = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **extra}
    if _mqtt_client:
        try:
            _mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            print(f"[topology] event publish error: {e}")


def _affected_devices(line: dict) -> list[str]:
    nodes = {n["node_id"]: n for n in _topology.get("nodes", [])}
    devices = []
    for key in ("from_node_id", "to_node_id"):
        node = nodes.get(line.get(key, ""))
        if node:
            devices.append(node["resource_id"])
    return devices


def publish_line_state(line: dict) -> None:
    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    topic = f"{plant_id}/topology/line/{line['line_id']}"
    payload = {
        "line_id": line["line_id"],
        "status": line["status"],
        "from_node_id": line["from_node_id"],
        "to_node_id": line["to_node_id"],
        "affected_devices": _affected_devices(line),
    }
    publish(topic, payload)


def publish_switch_state(line: dict) -> None:
    sw = line.get("switch")
    if not sw:
        return
    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    topic = f"{plant_id}/topology/switch/{sw['switch_id']}"
    payload = {
        "switch_id": sw["switch_id"],
        "line_id": line["line_id"],
        "position": sw["position"],
        "affected_devices": _affected_devices(line),
    }
    publish(topic, payload)


def publish_switch_telemetry(line: dict) -> None:
    sw = line.get("switch")
    if not sw:
        return
    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    topic = f"{plant_id}/switch/{sw['switch_id']}/telemetry"
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {
            "status": {
                "switch_state": sw["position"],
                "switch_type": sw.get("switch_type", "CB"),
                "controllable": sw.get("controllable", True),
                "interlock_blocked": sw.get("interlock_blocked", False),
                "last_transition_at": sw.get("last_transition_at"),
            }
        },
    }
    publish(topic, payload)


def republish_all() -> None:
    for line in _topology.get("lines", []):
        publish_line_state(line)
        publish_switch_state(line)
        publish_switch_telemetry(line)
