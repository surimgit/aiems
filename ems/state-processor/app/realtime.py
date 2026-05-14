from flask import request
from flask_socketio import join_room, leave_room

from .extensions import socketio


STATUS_NAMESPACE = "/status"


def _site_room(site_id: str) -> str:
    return f"site:{site_id}"


@socketio.on("connect", namespace=STATUS_NAMESPACE)
def on_status_connect(auth=None):
    print(f"[state-processor][socket] connected sid={request.sid}")


@socketio.on("disconnect", namespace=STATUS_NAMESPACE)
def on_status_disconnect():
    print(f"[state-processor][socket] disconnected sid={request.sid}")


@socketio.on("subscribe_site", namespace=STATUS_NAMESPACE)
def on_subscribe_site(payload):
    site_id = (payload or {}).get("site_id")
    if not site_id:
        return {"ok": False, "error": "site_id is required"}

    join_room(_site_room(site_id))
    return {"ok": True, "site_id": site_id}


@socketio.on("unsubscribe_site", namespace=STATUS_NAMESPACE)
def on_unsubscribe_site(payload):
    site_id = (payload or {}).get("site_id")
    if not site_id:
        return {"ok": False, "error": "site_id is required"}

    leave_room(_site_room(site_id))
    return {"ok": True, "site_id": site_id}


def emit_state_update(snapshot: dict) -> None:
    site_id = snapshot.get("site_id")
    event = {
        "type": "state_update",
        "timestamp": snapshot.get("calculated_at") or snapshot.get("timestamp"),
        "site_id": site_id,
        "edge_id": snapshot.get("edge_id"),
        "device_id": snapshot.get("device_id"),
        "resource_type": snapshot.get("resource_type"),
        "location": snapshot.get("location"),
        "latitude": snapshot.get("latitude"),
        "longitude": snapshot.get("longitude"),
        "data": snapshot,
    }

    socketio.emit("state_update", event, namespace=STATUS_NAMESPACE)
    if site_id:
        socketio.emit(
            "site_state_update",
            event,
            namespace=STATUS_NAMESPACE,
            room=_site_room(site_id),
        )
