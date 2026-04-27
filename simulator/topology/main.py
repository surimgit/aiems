from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml
import paho.mqtt.client as mqtt

PORT = int(os.environ.get("PORT", 8081))
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPOLOGY_PATH = Path(os.environ.get("TOPOLOGY_PATH", "/app/topology.yaml"))
STATIC_DIR = Path(__file__).parent / "static"

_topology: dict = {}
_lock = threading.Lock()
_mqtt_client: mqtt.Client | None = None


# ── YAML persistence ─────────────────────────────────────────────────────────

def _load_topology() -> dict:
    if not TOPOLOGY_PATH.exists():
        return {"plant_id": "PLANT-ALPHA", "nodes": [], "lines": []}
    return yaml.safe_load(TOPOLOGY_PATH.read_text(encoding="utf-8")) or {}


def _save_topology() -> None:
    with open(TOPOLOGY_PATH, "w", encoding="utf-8") as f:
        yaml.dump(_topology, f, default_flow_style=False, allow_unicode=True)


# ── MQTT ─────────────────────────────────────────────────────────────────────

def _mqtt_connect() -> None:
    global _mqtt_client

    def on_connect(client, userdata, flags, rc, props=None):
        print(f"[topology] MQTT connected (rc={rc})")
        plant_id = _topology.get("plant_id", "PLANT-ALPHA")
        cmd_topic = f"{plant_id}/switch/+/command"
        client.subscribe(cmd_topic)
        print(f"[topology] subscribed to {cmd_topic}")

    def on_message(client, userdata, message):
        topic = message.topic
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            return
        parts = topic.split("/")
        # {plant_id}/switch/{switch_id}/command
        if len(parts) == 4 and parts[1] == "switch" and parts[3] == "command":
            switch_id = parts[2]
            threading.Thread(
                target=_handle_switch_command,
                args=(switch_id, payload),
                daemon=True,
            ).start()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()
            _mqtt_client = client
            print(f"[topology] MQTT connected to {MQTT_HOST}:{MQTT_PORT}")
            return
        except Exception as e:
            print(f"[topology] MQTT connection failed: {e}. Retrying in 5s...")
            time.sleep(5)


def _publish(topic: str, payload: dict) -> None:
    if _mqtt_client is None:
        return
    try:
        _mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False), retain=True)
    except Exception as e:
        print(f"[topology] publish error: {e}")


def _publish_event(event: str, extra: dict) -> None:
    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    topic = f"{plant_id}/topology/event"
    payload = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat(), **extra}
    if _mqtt_client:
        try:
            _mqtt_client.publish(topic, json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            print(f"[topology] event publish error: {e}")


def _affected_devices(line: dict) -> list[str]:
    """Line의 from/to node에 연결된 resource_id 목록 반환."""
    nodes = {n["node_id"]: n for n in _topology.get("nodes", [])}
    devices = []
    for key in ("from_node_id", "to_node_id"):
        node = nodes.get(line.get(key, ""))
        if node:
            devices.append(node["resource_id"])
    return devices


def _publish_line_state(line: dict) -> None:
    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    topic = f"{plant_id}/topology/line/{line['line_id']}"
    payload = {
        "line_id": line["line_id"],
        "status": line["status"],
        "from_node_id": line["from_node_id"],
        "to_node_id": line["to_node_id"],
        "affected_devices": _affected_devices(line),
    }
    _publish(topic, payload)


def _publish_switch_state(line: dict) -> None:
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
    _publish(topic, payload)


def _publish_switch_telemetry(line: dict) -> None:
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
    _publish(topic, payload)


def _republish_all() -> None:
    """브로커 재연결 시 전체 상태를 retained로 재발행."""
    for line in _topology.get("lines", []):
        _publish_line_state(line)
        _publish_switch_state(line)
        _publish_switch_telemetry(line)


# ── Topology helpers ──────────────────────────────────────────────────────────

def _find_line(line_id: str) -> dict | None:
    for line in _topology.get("lines", []):
        if line["line_id"] == line_id:
            return line
    return None


def _find_switch_line(switch_id: str) -> dict | None:
    for line in _topology.get("lines", []):
        sw = line.get("switch", {})
        if sw.get("switch_id") == switch_id:
            return line
    return None


# ── Business logic ───────────────────────────────────────────────────────────

def get_topology() -> dict:
    with _lock:
        return json.loads(json.dumps(_topology))


def create_line(body: dict) -> dict:
    line_id = body.get("line_id", "").strip()
    from_node = body.get("from_node_id", "").strip()
    to_node = body.get("to_node_id", "").strip()
    if not line_id:
        raise ValueError("line_id is required")
    if not from_node or not to_node:
        raise ValueError("from_node_id and to_node_id are required")

    with _lock:
        if _find_line(line_id):
            raise ValueError(f"line '{line_id}' already exists")

        # 양방향 중복 체크 (A→B이든 B→A이든 이미 연결된 쌍이면 거부)
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
        _save_topology()
        _publish_line_state(line)
        _publish_switch_state(line)
        _publish_switch_telemetry(line)

    return {"line_id": line_id, "status": "created"}


def update_line(line_id: str, body: dict) -> dict:
    """ISOLATE_LINE / RESTORE_LINE"""
    command = body.get("command", "").upper()
    if command not in ("ISOLATE_LINE", "RESTORE_LINE"):
        raise ValueError("command must be ISOLATE_LINE or RESTORE_LINE")

    with _lock:
        line = _find_line(line_id)
        if line is None:
            raise FileNotFoundError(f"line '{line_id}' not found")

        sw = line.get("switch", {})
        if sw.get("interlock_blocked"):
            raise ValueError("line control blocked by interlock")

        new_status = "BLOCKED" if command == "ISOLATE_LINE" else "NORMAL"
        line["status"] = new_status
        _save_topology()
        _publish_line_state(line)

    event = "LINE_BLOCKED" if new_status == "BLOCKED" else "LINE_RESTORED"
    _publish_event(event, {"line_id": line_id})
    print(f"[topology] {event}: {line_id}")
    return {"line_id": line_id, "status": new_status}


def inject_line_fault(line_id: str, fault: bool) -> dict:
    """LINE_FAULT / LINE_RESTORE — 장애 주입용."""
    with _lock:
        line = _find_line(line_id)
        if line is None:
            raise FileNotFoundError(f"line '{line_id}' not found")

        line["status"] = "FAULT" if fault else "NORMAL"
        _save_topology()
        _publish_line_state(line)

    event = "LINE_FAULT" if fault else "LINE_RESTORED"
    _publish_event(event, {"line_id": line_id})
    print(f"[topology] {event}: {line_id}")
    return {"line_id": line_id, "status": line["status"]}


def update_switch(switch_id: str, body: dict) -> dict:
    """OPEN_SWITCH / CLOSE_SWITCH"""
    command = body.get("command", "").upper()
    if command not in ("OPEN_SWITCH", "CLOSE_SWITCH"):
        raise ValueError("command must be OPEN_SWITCH or CLOSE_SWITCH")

    with _lock:
        line = _find_switch_line(switch_id)
        if line is None:
            raise FileNotFoundError(f"switch '{switch_id}' not found")

        sw = line["switch"]
        if sw.get("interlock_blocked"):
            raise ValueError("switch control blocked by interlock")
        if not sw.get("controllable", True):
            raise ValueError("switch is not controllable")

        sw["position"] = "TRANSITIONING"
        _publish_switch_state(line)
        _publish_switch_telemetry(line)

        new_position = "OPEN" if command == "OPEN_SWITCH" else "CLOSED"
        sw["position"] = new_position
        sw["last_transition_at"] = datetime.now(timezone.utc).isoformat()
        _save_topology()
        _publish_switch_state(line)
        _publish_switch_telemetry(line)

    event = "SWITCH_OPENED" if new_position == "OPEN" else "SWITCH_CLOSED"
    _publish_event(event, {"switch_id": switch_id, "line_id": line["line_id"]})
    print(f"[topology] {event}: {switch_id}")
    return {"switch_id": switch_id, "position": new_position}


def _handle_switch_command(switch_id: str, raw_payload: dict) -> None:
    command_id = raw_payload.get("command_id", "unknown")
    command_type = str(raw_payload.get("command_type", "")).lower()
    cmd_payload = raw_payload.get("payload", {})

    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    ack_topic = f"{plant_id}/switch/{switch_id}/ack"

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

    # mode_change RESET — FAULT → UNKNOWN 복구
    if command_type == "mode_change":
        action = cmd_payload.get("action", "")
        if action != "RESET":
            _reject(f"unknown action: {action}")
            return
        with _lock:
            line = _find_switch_line(switch_id)
            if line is None:
                _reject(f"switch '{switch_id}' not found")
                return
            sw = line["switch"]
            if sw.get("position") != "FAULT":
                _reject("switch is not in FAULT state")
                return
            sw["position"] = "UNKNOWN"
            sw["controllable"] = True
            _save_topology()
            _publish_switch_state(line)
            _publish_switch_telemetry(line)
        _accept()
        print(f"[topology] SWITCH_RESET: {switch_id}")
        return

    if command_type not in ("open", "close"):
        _reject(f"unknown command_type: {command_type}")
        return

    with _lock:
        line = _find_switch_line(switch_id)
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
        _save_topology()
        _publish_switch_state(line)
        _publish_switch_telemetry(line)

    _accept()

    new_position = "OPEN" if command_type == "open" else "CLOSED"

    def _on_fault_timeout():
        with _lock:
            timed_line = _find_switch_line(switch_id)
            if timed_line is None:
                return
            timed_sw = timed_line["switch"]
            if timed_sw.get("position") != "TRANSITIONING":
                return
            timed_sw["position"] = "FAULT"
            timed_sw["controllable"] = False
            _save_topology()
            _publish_switch_state(timed_line)
            _publish_switch_telemetry(timed_line)
        _publish_event("SWITCH_FAILED", {"switch_id": switch_id, "event_code": "EVT-E-006"})
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
            trans_line = _find_switch_line(switch_id)
            if trans_line is None:
                return
            trans_sw = trans_line["switch"]
            if trans_sw.get("position") != "TRANSITIONING":
                return
            line_id = trans_line["line_id"]
            trans_sw["position"] = new_position
            trans_sw["last_transition_at"] = datetime.now(timezone.utc).isoformat()
            _save_topology()
            _publish_switch_state(trans_line)
            _publish_switch_telemetry(trans_line)
        event = "SWITCH_OPENED" if new_position == "OPEN" else "SWITCH_CLOSED"
        _publish_event(event, {"switch_id": switch_id, "line_id": line_id})
        print(f"[topology] {event}: {switch_id}")

    threading.Thread(target=_do_transition, daemon=True).start()


def delete_line(line_id: str) -> dict:
    with _lock:
        line = _find_line(line_id)
        if line is None:
            raise FileNotFoundError(f"line '{line_id}' not found")
        _topology["lines"] = [l for l in _topology["lines"] if l["line_id"] != line_id]
        _save_topology()

    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    if _mqtt_client:
        _mqtt_client.publish(f"{plant_id}/topology/line/{line_id}", "", retain=True)
    return {"line_id": line_id, "status": "deleted"}


# ── Node CRUD ─────────────────────────────────────────────────────────────────

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
        # 이미 존재하면 upsert (idempotent)
        for i, n in enumerate(nodes):
            if n["node_id"] == node_id:
                nodes[i] = {"node_id": node_id, "node_type": node_type,
                             "edge_id": edge_id, "resource_id": resource_id}
                _save_topology()
                return {"node_id": node_id, "status": "updated"}
        nodes.append({"node_id": node_id, "node_type": node_type,
                       "edge_id": edge_id, "resource_id": resource_id})
        _save_topology()

    return {"node_id": node_id, "status": "created"}


def delete_node(node_id: str) -> dict:
    """노드 삭제 + 해당 노드가 양 끝인 라인도 함께 삭제."""
    with _lock:
        nodes = _topology.get("nodes", [])
        if not any(n["node_id"] == node_id for n in nodes):
            raise FileNotFoundError(f"node '{node_id}' not found")

        # 연결된 라인 수집 후 삭제
        removed_lines = [
            l for l in _topology.get("lines", [])
            if l["from_node_id"] == node_id or l["to_node_id"] == node_id
        ]
        _topology["lines"] = [
            l for l in _topology.get("lines", [])
            if l["from_node_id"] != node_id and l["to_node_id"] != node_id
        ]
        _topology["nodes"] = [n for n in nodes if n["node_id"] != node_id]
        _save_topology()

    plant_id = _topology.get("plant_id", "PLANT-ALPHA")
    if _mqtt_client:
        for line in removed_lines:
            _mqtt_client.publish(f"{plant_id}/topology/line/{line['line_id']}", "", retain=True)

    return {"node_id": node_id, "status": "deleted", "removed_lines": [l["line_id"] for l in removed_lines]}


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _send_json(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_err(handler: BaseHTTPRequestHandler, message: str, status: int = 400) -> None:
    _send_json(handler, {"error": message}, status)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))


# ── HTTP handler ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        print(f"[GET] {p}")

        if p in ("/", "/index.html"):
            return self._serve_file(STATIC_DIR / "index.html")
        if p.startswith("/static/"):
            return self._serve_file(STATIC_DIR / p[len("/static/"):])
        if p == "/api/topology":
            return _send_json(self, get_topology())

        _send_err(self, "Not found", 404)

    def do_POST(self):
        p = self.path
        print(f"[POST] {p}")

        if p == "/api/lines":
            try:
                return _send_json(self, create_line(_read_body(self)), 201)
            except ValueError as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        if p == "/api/nodes":
            try:
                return _send_json(self, create_node(_read_body(self)), 201)
            except ValueError as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        _send_err(self, "Not found", 404)

    def do_PATCH(self):
        p = self.path
        print(f"[PATCH] {p}")

        m = re.match(r"^/api/lines/([^/]+)$", p)
        if m:
            line_id = m.group(1)
            try:
                body = _read_body(self)
                # fault 주입용 단축 경로
                if "fault" in body:
                    return _send_json(self, inject_line_fault(line_id, bool(body["fault"])))
                return _send_json(self, update_line(line_id, body))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except ValueError as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        m = re.match(r"^/api/switches/([^/]+)$", p)
        if m:
            switch_id = m.group(1)
            try:
                return _send_json(self, update_switch(switch_id, _read_body(self)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except ValueError as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        _send_err(self, "Not found", 404)

    def do_DELETE(self):
        p = self.path
        print(f"[DELETE] {p}")

        m = re.match(r"^/api/lines/([^/]+)$", p)
        if m:
            try:
                return _send_json(self, delete_line(m.group(1)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except Exception as e:
                return _send_err(self, str(e), 500)

        m = re.match(r"^/api/nodes/([^/]+)$", p)
        if m:
            try:
                return _send_json(self, delete_node(m.group(1)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except Exception as e:
                return _send_err(self, str(e), 500)

        _send_err(self, "Not found", 404)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return _send_err(self, "Not found", 404)
        content_type, _ = mimetypes.guess_type(str(path))
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _topology.update(_load_topology())
    print(f"[topology] loaded: {len(_topology.get('nodes', []))} nodes, {len(_topology.get('lines', []))} lines")

    threading.Thread(target=_mqtt_connect, daemon=True).start()
    # MQTT 연결 대기 후 초기 상태 발행
    def _initial_publish():
        time.sleep(3)
        _republish_all()
        print("[topology] initial state published")
    threading.Thread(target=_initial_publish, daemon=True).start()

    print(f"[topology] listening: http://0.0.0.0:{PORT}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
