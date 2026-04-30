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

    envelope = {
        "message_type": message_type,
        "schema_version": "1.0",
        "site_id": site_id,
        "resource_id": device_id,
        "resource_type": resource_type.upper(),
        "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "source": "edge-simulator",
        "trace_id": f"trc-{uuid.uuid4().hex[:12]}",
        "payload": data.get("data", {}),
    }

    # event/emergency 메시지는 상위 필드(event_type, severity, message)를 보존
    for field in ("event_type", "severity", "message"):
        if field in data:
            envelope[field] = data[field]

    return envelope
