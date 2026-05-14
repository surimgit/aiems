# plz commit

import asyncio
import json
from datetime import datetime, timezone
import aiomqtt
import redis.asyncio as aioredis
from ..config import (
    MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD,
    SITE_ID, REDIS_HOST, REDIS_PORT, REDIS_PASSWORD,
)
from ..domain.normalizer import normalize
from ..domain.classifier import classify
from .redis_publisher import RedisPublisher
from .telemetry_coalescer import TelemetryCoalescer


_HEARTBEAT_TTL_SEC = 30  # 시뮬레이터 10초 주기 × 3회 미수신 시 만료
_HEARTBEAT_PREFIX = "ems:heartbeat:"
_TOPOLOGY_PREFIX = "ems:topology:"

TOPICS = [
    f"{SITE_ID}/+/+/telemetry",
    f"{SITE_ID}/+/+/+/telemetry",
    f"{SITE_ID}/+/+/event",
    f"{SITE_ID}/+/+/+/event",
    f"{SITE_ID}/+/+/emergency",
    f"{SITE_ID}/+/+/+/emergency",
    f"{SITE_ID}/+/+/ack",
    f"{SITE_ID}/+/+/+/ack",
    f"{SITE_ID}/heartbeat",
    f"{SITE_ID}/simulator-manager/topology/structure/snapshot",
    f"{SITE_ID}/topology/line/+",
    f"{SITE_ID}/topology/switch/+",
]

_RECONNECT_DELAY_SEC = 5


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def run(publisher: RedisPublisher) -> None:
    redis = aioredis.Redis(
        host=REDIS_HOST, port=REDIS_PORT,
        password=REDIS_PASSWORD, decode_responses=True,
    )
    coalescer = TelemetryCoalescer(publisher)
    flush_task = asyncio.create_task(coalescer.run())
    try:
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=MQTT_HOST, port=MQTT_PORT,
                    username=MQTT_USER, password=MQTT_PASSWORD,
                ) as client:
                    for topic in TOPICS:
                        await client.subscribe(topic)
                    print(f"[ingestion] MQTT 구독 시작: {TOPICS}")

                    async for message in client.messages:
                        topic = str(message.topic)
                        try:
                            parts = topic.split("/")

                            if len(parts) == 2 and parts[1] == "heartbeat":
                                try:
                                    hb = json.loads(message.payload)
                                    device_id = hb.get("device_id") or hb.get("resource_id")
                                    edge_id = (
                                        hb.get("edge_id")
                                        or hb.get("edgeId")
                                        or hb.get("edgeID")
                                        or device_id
                                    )
                                    if device_id:
                                        timestamp = hb.get("timestamp", "")
                                        key = f"{_HEARTBEAT_PREFIX}{SITE_ID}:{device_id}"
                                        await redis.setex(key, _HEARTBEAT_TTL_SEC, timestamp)
                                        if edge_id and edge_id != device_id:
                                            edge_key = f"{_HEARTBEAT_PREFIX}{SITE_ID}:{edge_id}:{device_id}"
                                            await redis.setex(edge_key, _HEARTBEAT_TTL_SEC, timestamp)
                                        print(f"[ingestion] heartbeat: edge={edge_id} device={device_id}")
                                except Exception as e:
                                    print(f"[ingestion] heartbeat 파싱 실패: {e}")
                                continue

                            if _is_topology_snapshot_topic(parts):
                                try:
                                    payload = json.loads(message.payload)
                                    await _apply_topology_snapshot(redis, payload)
                                except Exception as e:
                                    print(f"[ingestion] topology snapshot 처리 실패: {e}")
                                continue

                            if _is_topology_state_topic(parts):
                                try:
                                    payload = json.loads(message.payload)
                                    await _apply_topology_state(redis, parts[0], parts[2], payload)
                                except Exception as e:
                                    print(f"[ingestion] topology state 처리 실패: {e}")
                                continue

                            if not _is_device_message_topic(parts):
                                print(f"[ingestion] 지원하지 않는 topic 무시: {topic}")
                                continue

                            message_type = parts[-1]
                            if message_type == "ack":
                                continue  # ACK는 control이 직접 처리, state stream 불필요
                            envelope = normalize(topic, message.payload)
                            stream = classify(message_type)

                            if message_type == "telemetry":
                                await coalescer.add(stream, envelope)
                            else:
                                await publisher.publish(stream, envelope)
                                print(f"[ingestion] {topic} → {stream}")
                        except Exception as e:
                            print(f"[ingestion] 처리 실패 topic={topic} error={e}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[ingestion] MQTT 연결 끊김: {e} — {_RECONNECT_DELAY_SEC}s 후 재연결")
                await asyncio.sleep(_RECONNECT_DELAY_SEC)
    finally:
        flush_task.cancel()
        try:
            await flush_task
        except asyncio.CancelledError:
            pass
        await coalescer.flush()
        await redis.aclose()


def _is_topology_snapshot_topic(parts: list[str]) -> bool:
    return len(parts) == 5 and parts[1:5] == ["simulator-manager", "topology", "structure", "snapshot"]


def _is_topology_state_topic(parts: list[str]) -> bool:
    return len(parts) == 4 and parts[1] == "topology" and parts[2] in ("line", "switch")


def _is_device_message_topic(parts: list[str]) -> bool:
    if len(parts) == 4:
        return parts[3] in ("telemetry", "event", "emergency", "ack")
    if len(parts) == 5:
        return parts[4] in ("telemetry", "event", "emergency", "ack")
    return False


async def _apply_topology_snapshot(redis, payload: dict) -> None:
    plant_id = payload.get("plant_id") or payload.get("site_id") or SITE_ID
    topology = payload.get("topology") or payload
    if not isinstance(topology, dict):
        return

    normalized = _normalize_topology(str(plant_id), topology)
    ttl_sec = int(float(payload.get("ttl_sec") or 30) * 3)
    entry = {
        "plant_id": plant_id,
        "source": payload.get("source", "simulator-manager"),
        "sequence": payload.get("sequence"),
        "updated_at": _utc_now_iso(),
        "ttl_sec": payload.get("ttl_sec", 30),
        "topology": normalized,
    }
    await redis.setex(f"{_TOPOLOGY_PREFIX}{plant_id}", max(ttl_sec, 30), json.dumps(entry, ensure_ascii=False))
    print(f"[ingestion] topology snapshot cached: {plant_id} seq={payload.get('sequence')}")


async def _apply_topology_state(redis, plant_id: str, kind: str, payload: dict) -> None:
    key = f"{_TOPOLOGY_PREFIX}{plant_id}"
    raw = await redis.get(key)
    if not raw:
        return
    entry = json.loads(raw)
    topology = entry.get("topology") or {}

    if kind == "line":
        line_id = payload.get("line_id")
        if not line_id:
            return
        lines = topology.setdefault("lines", [])
        if (payload.get("status") or "").upper() == "DELETED":
            topology["lines"] = [line for line in lines if line.get("line_id") != line_id]
        else:
            for line in lines:
                if line.get("line_id") == line_id:
                    for field in ("status", "from_node_id", "to_node_id", "flow_kw"):
                        if field in payload:
                            line[field] = payload[field]
                    break

    if kind == "switch":
        switch_id = payload.get("switch_id")
        if not switch_id:
            return
        switches = topology.setdefault("switches", [])
        if (payload.get("position") or "").upper() == "DELETED":
            topology["switches"] = [sw for sw in switches if sw.get("switch_id") != switch_id]
        else:
            for sw in switches:
                if sw.get("switch_id") == switch_id:
                    for field in ("position", "line_id", "controllable", "interlock_blocked"):
                        if field in payload:
                            sw[field] = payload[field]
                    break

    entry["topology"] = topology
    entry["updated_at"] = _utc_now_iso()
    ttl_sec = int(float(entry.get("ttl_sec") or 30) * 3)
    await redis.setex(key, max(ttl_sec, 30), json.dumps(entry, ensure_ascii=False))


def _normalize_topology(plant_id: str, topology: dict) -> dict:
    nodes = []
    for node in topology.get("nodes", []) or []:
        pos = node.get("position") or {}
        nodes.append({
            "node_id": node.get("node_id"),
            "node_type": node.get("node_type") or "BUS",
            "resource_id": node.get("resource_id") or node.get("edge_id"),
            "position": {
                "x": float(pos.get("x") or 0.0),
                "y": float(pos.get("y") or 0.0),
            },
            "status": node.get("status") or "NORMAL",
        })

    lines = []
    switches_by_id = {}
    for line in topology.get("lines", []) or []:
        flow_kw = float(line.get("flow_kw") or 0.0)
        line_id = line.get("line_id")
        lines.append({
            "line_id": line_id,
            "from_node_id": line.get("from_node_id"),
            "to_node_id": line.get("to_node_id"),
            "direction": _direction(flow_kw),
            "flow_kw": round(flow_kw, 2),
            "status": (line.get("status") or "NORMAL").upper(),
        })
        sw = line.get("switch") or {}
        if sw.get("switch_id"):
            switches_by_id[sw["switch_id"]] = {
                "switch_id": sw.get("switch_id"),
                "line_id": line_id,
                "position": (sw.get("position") or "UNKNOWN").upper(),
                "controllable": bool(sw.get("controllable", True)),
                "interlock_blocked": bool(sw.get("interlock_blocked", False)),
            }

    for sw in topology.get("switches", []) or []:
        switch_id = sw.get("switch_id")
        if not switch_id:
            continue
        switches_by_id[switch_id] = {
            "switch_id": switch_id,
            "line_id": sw.get("line_id"),
            "position": (sw.get("position") or "UNKNOWN").upper(),
            "controllable": bool(sw.get("controllable", True)),
            "interlock_blocked": bool(sw.get("interlock_blocked", False)),
        }

    return {
        "site_id": plant_id,
        "nodes": [node for node in nodes if node.get("node_id")],
        "lines": [line for line in lines if line.get("line_id")],
        "switches": list(switches_by_id.values()),
    }


def _direction(flow_kw: float) -> str:
    if flow_kw > 0.01:
        return "FORWARD"
    if flow_kw < -0.01:
        return "REVERSE"
    return "BIDIRECTIONAL"
