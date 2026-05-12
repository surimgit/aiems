import json
import uuid
from datetime import datetime, timezone


def normalize(topic: str, raw_payload: bytes) -> dict:
    parts = topic.split("/")
    site_id = parts[0]
    resource_type = parts[1]
    device_id = parts[2]
    message_type = parts[3]

    data = json.loads(raw_payload)
    payload = data.get("data", {})
    if not isinstance(payload, dict):
        payload = {}
    edge_id = _extract_edge_id(device_id, data)
    location = _extract_location(data)

    envelope = {
        "message_type": message_type,
        "schema_version": "1.0",
        "site_id": site_id,
        "edge_id": edge_id,
        "resource_id": device_id,
        "resource_type": resource_type.upper(),
        "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": "edge-simulator",
        "trace_id": f"trc-{uuid.uuid4().hex[:12]}",
        "payload": payload,
    }
    if location:
        envelope["location"] = location
        envelope["latitude"] = location["latitude"]
        envelope["longitude"] = location["longitude"]

    # event/emergency 메시지는 상위 필드(event_type, severity, message)를 보존
    for field in ("event_type", "severity", "message"):
        if field in data:
            envelope[field] = data[field]

    return envelope


def _extract_edge_id(topic_device_id: str, data: dict) -> str:
    for source in (data, _as_dict(data.get("edge")), _as_dict(data.get("data"))):
        value = _first_present(source, ("edge_id", "edgeId", "edgeID", "device_id", "deviceId"))
        if value:
            return str(value)
    return topic_device_id


def _extract_location(data: dict) -> dict | None:
    payload = _as_dict(data.get("data"))
    candidates = [
        data,
        _as_dict(data.get("location")),
        _as_dict(data.get("geo")),
        _as_dict(data.get("position")),
        _as_dict(data.get("site")),
        _as_dict(data.get("edge")),
        payload,
    ]
    candidates.extend([
        _as_dict(payload.get("location")),
        _as_dict(payload.get("geo")),
        _as_dict(payload.get("position")),
    ])

    for source in candidates:
        latitude = _to_float(_first_present(source, ("latitude", "lat", "y")))
        longitude = _to_float(_first_present(source, ("longitude", "lon", "lng", "x")))
        if latitude is not None and longitude is not None:
            return {
                "latitude": latitude,
                "longitude": longitude,
            }
    return None


def _first_present(source: dict, keys: tuple[str, ...]):
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def _as_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _to_float(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
