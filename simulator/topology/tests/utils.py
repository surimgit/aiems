"""공통 유틸리티: MQTT 메시지 캡처, HTTP 헬퍼, 엣지 라이프사이클."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt
import requests

# ── 환경 설정 ─────────────────────────────────────────────────────────────────
MQTT_HOST = os.environ.get("MQTT_HOST", "host.docker.internal")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
SM_URL    = os.environ.get("SM_URL", "http://simulator-manager:8080")
TOPO_URL  = os.environ.get("TOPO_URL", "http://topology:8081")
PLANT_ID  = os.environ.get("PLANT_ID", "PLANT-ALPHA")

EDGE_STARTUP_SEC   = 15   # 컨테이너 기동 대기
FAULT_PROPAGATE_SEC = 2   # MQTT retained → 시뮬레이터 반영 대기
TELEMETRY_TIMEOUT  = 15   # 메시지 수집 최대 대기 시간

# ESS 디바이스 생성 시 pydantic 필수 필드 기본값
ESS_DEVICE_DEFAULTS = {
    "resource_type": "ess",
    "publish_interval_sec": 0.5,
    "initial_soc": 62.0,
    "power_limit_kw": 42.0,
    "capacity_kwh": 420.0,
    "low_soc_threshold": 20.0,
    "high_soc_threshold": 90.0,
    "min_safe_soc_threshold": 10.0,
    "max_safe_soc_threshold": 95.0,
    "temperature_c": 24.5,
    "max_temperature_c": 45.0,
    "profile": {
        "module": "core.profiles.default_profile",
        "class_name": "DefaultEssProfile",
        "seed": 101,
    },
}


# ── MQTT 캡처 ─────────────────────────────────────────────────────────────────

class MqttCapture:
    """지정 토픽의 telemetry 메시지를 스레드-안전하게 수집한다."""

    def __init__(self):
        self._msgs: list[dict] = []
        self._lock = threading.Lock()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_message = self._on_message
        self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        self._client.loop_start()

    def subscribe(self, topic: str) -> None:
        self._client.subscribe(topic)

    def _on_message(self, _c, _u, msg: Any) -> None:
        try:
            payload = json.loads(msg.payload.decode())
            with self._lock:
                self._msgs.append({"topic": msg.topic, "payload": payload})
        except Exception:
            pass

    def collect(self, count: int, timeout: float = TELEMETRY_TIMEOUT) -> list[dict]:
        """count개 메시지가 쌓일 때까지 기다렸다가 반환."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if len(self._msgs) >= count:
                    result = self._msgs[:count]
                    self._msgs = self._msgs[count:]
                    return result
            time.sleep(0.1)
        with self._lock:
            result = list(self._msgs)
            self._msgs = []
        return result

    def clear(self) -> None:
        with self._lock:
            self._msgs.clear()

    def publish(self, topic: str, payload: dict) -> None:
        self._client.publish(topic, json.dumps(payload))

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()


# ── HTTP 헬퍼 ─────────────────────────────────────────────────────────────────

def sm(method: str, path: str, body: dict | None = None) -> dict:
    """simulator-manager REST 호출."""
    url = SM_URL + path
    r = requests.request(method, url, json=body, timeout=10)
    r.raise_for_status()
    return r.json()


def topo(method: str, path: str, body: dict | None = None) -> dict:
    """topology REST 호출."""
    url = TOPO_URL + path
    r = requests.request(method, url, json=body, timeout=10)
    r.raise_for_status()
    return r.json()


# ── 엣지 라이프사이클 ─────────────────────────────────────────────────────────

def create_edge(edge_type: str, edge_id: str, device_id: str,
                extra_device_fields: dict | None = None) -> None:
    """엣지 생성 → (자동 시드된 device가 다르면) 디바이스 추가 → 기동 대기.
    simulator-manager가 edge 생성 시 기본 device 1개를 자동 시드하므로,
    test가 요청한 device_id가 그것과 다를 때만 add_device 호출.
    """
    sm("POST", "/api/edges", {"edge_type": edge_type, "edge_id": edge_id})

    # 자동 시드된 device 목록 조회
    seeded = sm("GET", f"/api/edges/{edge_id}/devices") or []
    seeded_ids = {d.get("device_id") for d in seeded}

    if device_id not in seeded_ids:
        device_body = {"device_id": device_id}
        if extra_device_fields:
            device_body.update(extra_device_fields)
        sm("POST", f"/api/edges/{edge_id}/devices", device_body)

    print(f"  [setup] {edge_id} 기동 대기 ({EDGE_STARTUP_SEC}s)...")
    time.sleep(EDGE_STARTUP_SEC)


def delete_edge(edge_id: str) -> None:
    """엣지 삭제 (실패해도 무시)."""
    try:
        sm("DELETE", f"/api/edges/{edge_id}")
        print(f"  [teardown] {edge_id} 삭제 완료")
    except Exception as e:
        print(f"  [teardown] {edge_id} 삭제 실패 (무시): {e}")


def create_test_line(line_id: str, from_edge_id: str, to_edge_id: str,
                     switch_id: str | None = None) -> None:
    """테스트 전용 line을 topology에 추가.
    from_edge_id / to_edge_id 는 테스트가 create_edge로 만든 격리 edge들이어야 한다.
    """
    body = {
        "line_id": line_id,
        "from_node_id": f"node-{from_edge_id}",
        "to_node_id": f"node-{to_edge_id}",
    }
    if switch_id:
        body["switch_id"] = switch_id
    topo("POST", "/api/lines", body)


def cleanup_test_line(line_id: str) -> None:
    """테스트 전용 line 삭제 (실패해도 무시)."""
    try:
        topo("DELETE", f"/api/lines/{line_id}")
    except Exception:
        pass


def restore_topology() -> None:
    """모든 선로와 스위치를 정상 상태로 복원."""
    try:
        data = topo("GET", "/api/topology")
        for line in data.get("lines", []):
            if line["status"] != "NORMAL":
                topo("PATCH", f"/api/lines/{line['line_id']}", {"fault": False})
                topo("PATCH", f"/api/lines/{line['line_id']}", {"command": "RESTORE_LINE"})
            sw = line.get("switch", {})
            if sw.get("position") not in ("CLOSED", "TRANSITIONING"):
                topo("PATCH", f"/api/switches/{sw['switch_id']}", {"command": "CLOSE_SWITCH"})
        time.sleep(FAULT_PROPAGATE_SEC)
    except Exception as e:
        print(f"  [teardown] topology 복원 실패: {e}")


# ── 단언 헬퍼 ─────────────────────────────────────────────────────────────────

def assert_telemetry(msgs: list[dict], *, min_count: int = 1,
                     comms_health: str | None = None,
                     p_zero: bool | None = None,
                     soc_frozen: bool | None = None) -> None:
    """수집된 telemetry 메시지에 대해 조건 검증."""
    assert len(msgs) >= min_count, (
        f"메시지 수 부족: {len(msgs)} < {min_count}"
    )
    for msg in msgs:
        data = msg["payload"].get("data", {})
        inst = data.get("instantaneous", {})
        status = data.get("status", {})

        if comms_health is not None:
            actual = status.get("comms_health")
            assert actual == comms_health, (
                f"comms_health 불일치: expected={comms_health!r}, got={actual!r}\n"
                f"payload: {json.dumps(msg['payload'], indent=2)}"
            )

        if p_zero is True:
            p = inst.get("P", -1)
            assert p == 0.0, f"P 값이 0이어야 함: got P={p}"

        if p_zero is False:
            p = inst.get("P", 0)
            assert p > 0, f"P 값이 0보다 커야 함: got P={p}"

    if soc_frozen is True and len(msgs) >= 2:
        socs = [m["payload"]["data"]["status"]["SOC"] for m in msgs
                if "SOC" in m["payload"].get("data", {}).get("status", {})]
        assert len(set(socs)) == 1, (
            f"SOC 값이 고정되어야 함. 수집된 SOC: {socs}"
        )


def log_result(name: str, passed: bool, detail: str = "") -> None:
    mark = "✓ PASS" if passed else "✗ FAIL"
    print(f"  [{mark}] {name}" + (f": {detail}" if detail else ""))
