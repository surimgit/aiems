from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

import publisher
import repository
from state import _topology, _lock


def get_topology() -> dict:
    with _lock:
        return json.loads(json.dumps(_topology))


def create_node(body: dict) -> dict:
    node_id = body.get("node_id", "").strip()
    node_type = body.get("node_type", "").strip()
    edge_id = body.get("edge_id", "").strip()
    resource_id = body.get("resource_id", edge_id).strip()

    if not node_id:
        raise ValueError("node_id is required")
    if node_type not in ("GENERATION", "STORAGE", "LOAD"):
        raise ValueError("node_type must be GENERATION, STORAGE, or LOAD")

    with _lock:
        nodes = _topology.setdefault("nodes", [])
        for i, n in enumerate(nodes):
            if n["node_id"] == node_id:
                nodes[i] = {"node_id": node_id, "node_type": node_type,
                             "edge_id": edge_id, "resource_id": resource_id}
                repository.save()
                return {"node_id": node_id, "status": "updated"}
        nodes.append({"node_id": node_id, "node_type": node_type,
                       "edge_id": edge_id, "resource_id": resource_id})
        repository.save()

    return {"node_id": node_id, "status": "created"}


def delete_node(node_id: str) -> dict:
    with _lock:
        nodes = _topology.get("nodes", [])
        if not any(n["node_id"] == node_id for n in nodes):
            raise FileNotFoundError(f"node '{node_id}' not found")

        removed_lines = [
            line for line in _topology.get("lines", [])
            if line["from_node_id"] == node_id or line["to_node_id"] == node_id
        ]
        _topology["lines"] = [
            line for line in _topology.get("lines", [])
            if line["from_node_id"] != node_id and line["to_node_id"] != node_id
        ]
        _topology["nodes"] = [n for n in nodes if n["node_id"] != node_id]
        repository.save()

    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    from publisher import _mqtt_client
    if _mqtt_client:
        for line in removed_lines:
            _mqtt_client.publish(f"{plant_id}/topology/line/{line['line_id']}", "", retain=True)

    return {"node_id": node_id, "status": "deleted",
            "removed_lines": [line["line_id"] for line in removed_lines]}


def create_line(body: dict) -> dict:
    line_id = body.get("line_id", "").strip()
    from_node = body.get("from_node_id", "").strip()
    to_node = body.get("to_node_id", "").strip()
    if not line_id:
        raise ValueError("line_id is required")
    if not from_node or not to_node:
        raise ValueError("from_node_id and to_node_id are required")

    with _lock:
        if repository.find_line(line_id):
            raise ValueError(f"line '{line_id}' already exists")

        for existing in _topology.get("lines", []):
            if (existing["from_node_id"] == from_node and existing["to_node_id"] == to_node) or \
               (existing["from_node_id"] == to_node and existing["to_node_id"] == from_node):
                raise ValueError("이미 연결된 노드입니다")

        switch_id = body.get("switch_id", f"sw-{line_id}")
        line = {
            "line_id": line_id,
            "from_node_id": from_node,
            "to_node_id": to_node,
            "flow_kw": 0.0,
            "status": "NORMAL",
            "switch": {
                "switch_id": switch_id,
                "position": "CLOSED",
                "controllable": True,
                "interlock_blocked": False,
            },
        }
        _topology.setdefault("lines", []).append(line)
        repository.save()
        publisher.publish_line_state(line)
        publisher.publish_switch_state(line)
        publisher.publish_switch_telemetry(line)

    return {"line_id": line_id, "status": "created"}


def update_line(line_id: str, body: dict) -> dict:
    command = body.get("command", "").upper()
    if command not in ("ISOLATE_LINE", "RESTORE_LINE"):
        raise ValueError("command must be ISOLATE_LINE or RESTORE_LINE")

    with _lock:
        line = repository.find_line(line_id)
        if line is None:
            raise FileNotFoundError(f"line '{line_id}' not found")

        if line.get("switch", {}).get("interlock_blocked"):
            raise ValueError("line control blocked by interlock")

        new_status = "BLOCKED" if command == "ISOLATE_LINE" else "NORMAL"
        line["status"] = new_status
        repository.save()
        publisher.publish_line_state(line)

    event = "LINE_BLOCKED" if new_status == "BLOCKED" else "LINE_RESTORED"
    publisher.publish_event(event, {"line_id": line_id})
    print(f"[topology] {event}: {line_id}")
    return {"line_id": line_id, "status": new_status}


def inject_line_fault(line_id: str, fault: bool) -> dict:
    with _lock:
        line = repository.find_line(line_id)
        if line is None:
            raise FileNotFoundError(f"line '{line_id}' not found")

        line["status"] = "FAULT" if fault else "NORMAL"
        repository.save()
        publisher.publish_line_state(line)

    event = "LINE_FAULT" if fault else "LINE_RESTORED"
    publisher.publish_event(event, {"line_id": line_id})
    print(f"[topology] {event}: {line_id}")
    return {"line_id": line_id, "status": line["status"]}


def update_switch(switch_id: str, body: dict) -> dict:
    command = body.get("command", "").upper()
    if command not in ("OPEN_SWITCH", "CLOSE_SWITCH"):
        raise ValueError("command must be OPEN_SWITCH or CLOSE_SWITCH")

    with _lock:
        line = repository.find_switch_line(switch_id)
        if line is None:
            raise FileNotFoundError(f"switch '{switch_id}' not found")

        sw = line["switch"]
        if sw.get("interlock_blocked"):
            raise ValueError("switch control blocked by interlock")
        if not sw.get("controllable", True):
            raise ValueError("switch is not controllable")

        sw["position"] = "TRANSITIONING"
        publisher.publish_switch_state(line)
        publisher.publish_switch_telemetry(line)

        new_position = "OPEN" if command == "OPEN_SWITCH" else "CLOSED"
        sw["position"] = new_position
        sw["last_transition_at"] = datetime.now(timezone.utc).isoformat()
        repository.save()
        publisher.publish_switch_state(line)
        publisher.publish_switch_telemetry(line)

    event = "SWITCH_OPENED" if new_position == "OPEN" else "SWITCH_CLOSED"
    publisher.publish_event(event, {"switch_id": switch_id, "line_id": line["line_id"]})
    print(f"[topology] {event}: {switch_id}")
    return {"switch_id": switch_id, "position": new_position}


def delete_line(line_id: str) -> dict:
    with _lock:
        line = repository.find_line(line_id)
        if line is None:
            raise FileNotFoundError(f"line '{line_id}' not found")
        _topology["lines"] = [l for l in _topology["lines"] if l["line_id"] != line_id]
        repository.save()

    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    from publisher import _mqtt_client
    if _mqtt_client:
        _mqtt_client.publish(f"{plant_id}/topology/line/{line_id}", "", retain=True)
    return {"line_id": line_id, "status": "deleted"}


def handle_switch_command(switch_id: str, raw_payload: dict) -> None:
    command_id = raw_payload.get("command_id", "unknown")
    command_type = str(raw_payload.get("command_type", "")).lower()
    cmd_payload = raw_payload.get("payload", {})

    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    ack_topic = f"{plant_id}/switch/{switch_id}/ack"

    from publisher import _mqtt_client

    def _reject(reason: str) -> None:
        if _mqtt_client:
            _mqtt_client.publish(ack_topic, json.dumps(
                {"command_id": command_id, "status": "rejected", "reason": reason},
                ensure_ascii=False,
            ))

    def _accept() -> None:
        if _mqtt_client:
            _mqtt_client.publish(ack_topic, json.dumps(
                {"command_id": command_id, "status": "accepted"},
                ensure_ascii=False,
            ))

    if command_type == "mode_change":
        action = cmd_payload.get("action", "")
        if action != "RESET":
            _reject(f"unknown action: {action}")
            return
        with _lock:
            line = repository.find_switch_line(switch_id)
            if line is None:
                _reject(f"switch '{switch_id}' not found")
                return
            sw = line["switch"]
            if sw.get("position") != "FAULT":
                _reject("switch is not in FAULT state")
                return
            sw["position"] = "UNKNOWN"
            sw["controllable"] = True
            repository.save()
            publisher.publish_switch_state(line)
            publisher.publish_switch_telemetry(line)
        _accept()
        print(f"[topology] SWITCH_RESET: {switch_id}")
        return

    if command_type not in ("open", "close"):
        _reject(f"unknown command_type: {command_type}")
        return

    with _lock:
        line = repository.find_switch_line(switch_id)
        if line is None:
            _reject(f"switch '{switch_id}' not found")
            return
        sw = line["switch"]

        if sw.get("interlock_blocked"):
            _reject("switch control blocked by interlock")
            return
        if not sw.get("controllable", True):
            _reject("switch is not controllable")
            return
        if sw.get("position") == "TRANSITIONING":
            _reject("switch is already TRANSITIONING")
            return
        if sw.get("position") == "FAULT":
            _reject("switch is in FAULT state, send mode_change RESET first")
            return

        sw["position"] = "TRANSITIONING"
        repository.save()
        publisher.publish_switch_state(line)
        publisher.publish_switch_telemetry(line)

    _accept()

    new_position = "OPEN" if command_type == "open" else "CLOSED"

    def _on_fault_timeout():
        with _lock:
            timed_line = repository.find_switch_line(switch_id)
            if timed_line is None:
                return
            timed_sw = timed_line["switch"]
            if timed_sw.get("position") != "TRANSITIONING":
                return
            timed_sw["position"] = "FAULT"
            timed_sw["controllable"] = False
            repository.save()
            publisher.publish_switch_state(timed_line)
            publisher.publish_switch_telemetry(timed_line)
        publisher.publish_event("SWITCH_FAILED", {"switch_id": switch_id, "event_code": "EVT-E-006"})
        if _mqtt_client:
            emergency_topic = f"{plant_id}/switch/{switch_id}/emergency"
            _mqtt_client.publish(emergency_topic, json.dumps({
                "event_code": "EVT-E-006",
                "event_name": "SWITCH_FAILED",
                "switch_id": switch_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False))
        print(f"[topology] SWITCH_FAILED (timeout): {switch_id} → FAULT (EVT-E-006)")

    fault_timer = threading.Timer(5.0, _on_fault_timeout)
    fault_timer.start()

    def _do_transition():
        time.sleep(1.0)
        fault_timer.cancel()
        with _lock:
            trans_line = repository.find_switch_line(switch_id)
            if trans_line is None:
                return
            trans_sw = trans_line["switch"]
            if trans_sw.get("position") != "TRANSITIONING":
                return
            line_id = trans_line["line_id"]
            trans_sw["position"] = new_position
            trans_sw["last_transition_at"] = datetime.now(timezone.utc).isoformat()
            repository.save()
            publisher.publish_switch_state(trans_line)
            publisher.publish_switch_telemetry(trans_line)
        event = "SWITCH_OPENED" if new_position == "OPEN" else "SWITCH_CLOSED"
        publisher.publish_event(event, {"switch_id": switch_id, "line_id": line_id})
        print(f"[topology] {event}: {switch_id}")

    threading.Thread(target=_do_transition, daemon=True).start()
