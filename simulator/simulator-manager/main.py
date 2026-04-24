from __future__ import annotations

import json
import mimetypes
import os
import re
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

try:
    import docker
    _docker_client = docker.from_env()
    DOCKER_AVAILABLE = True
except Exception:
    _docker_client = None
    DOCKER_AVAILABLE = False

EDGES_DIR = Path(__file__).parent / "edges"
PORT = int(os.environ.get("PORT", 8080))
STATIC_DIR = Path(__file__).parent / "static"
DOCKER_NETWORK_NAME = os.environ.get("DOCKER_NETWORK", "ems_default")


def _detect_real_network_name() -> str:
    """
    현재 컨테이너가 속한 실제 Docker 네트워크 이름을 감지합니다.
    ems_default라는 이름이 포함된 네트워크가 있다면 최우선적으로 선택합니다.
    """
    if not DOCKER_AVAILABLE:
        return DOCKER_NETWORK_NAME

    try:
        import socket
        hostname = socket.gethostname()
        container = _docker_client.containers.get(hostname)
        networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        if networks:
            names = list(networks.keys())
            # 1순위: 환경변수 혹은 기본값과 정확히 일치하는 이름
            if DOCKER_NETWORK_NAME in names:
                return DOCKER_NETWORK_NAME
            # 2순위: ems_default 라는 문자열이 포함된 이름 (Docker Compose 접두사 고려)
            for name in names:
                if "ems_default" in name:
                    print(f"[manager] detected prefixed network: {name}")
                    return name
            # 3순위: 그냥 첫 번째 네트워크
            return names[0]
    except Exception as e:
        print(f"[manager] network auto-detect failed: {e}")
    
    return DOCKER_NETWORK_NAME


def _detect_host_edges_path() -> str:
    """호스트 절대경로 결정: 명시적 env → 컨테이너 마운트 자동 감지 → fallback."""
    explicit = os.environ.get("EDGES_HOST_PATH", "").strip()
    if explicit and os.path.isabs(explicit):
        return explicit

    # Docker 소켓으로 자신의 마운트 목록을 조회해 /app/edges 의 호스트 경로를 찾는다
    if DOCKER_AVAILABLE:
        try:
            import socket
            hostname = socket.gethostname()
            container = _docker_client.containers.get(hostname)
            for mount in container.attrs.get("Mounts", []):
                if mount.get("Destination") == "/app/edges":
                    src = mount.get("Source", "")
                    if src:
                        print(f"[manager] auto-detected host edges path: {src}")
                        return src
        except Exception as e:
            print(f"[manager] mount auto-detect failed: {e}")

    fallback = str(EDGES_DIR.resolve())
    print(f"[manager] using fallback edges path: {fallback}")
    return fallback


HOST_EDGES_PATH = _detect_host_edges_path()
REAL_NETWORK_NAME = _detect_real_network_name()

EDGE_TYPE_IMAGES = {
    "solar": os.environ.get("SOLAR_IMAGE", "solar-simulator:latest"),
    "diesel": os.environ.get("DIESEL_IMAGE", "diesel-simulator:latest"),
    "ess": os.environ.get("ESS_IMAGE", "ess-simulator:latest"),
    "load": os.environ.get("LOAD_IMAGE", "load-simulator:latest"),
}

EDGE_TYPE_CMD: dict[str, list[str] | None] = {
    "solar": None,
    "diesel": None,
    "ess": ["python", "main.py", "--no-cli"],
    "load": ["python", "main.py", "--scenario", "/app/config/scenario.yaml"],
}


# ── JSON helpers ────────────────────────────────────────────────────────────

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


# ── Edge / device file operations ───────────────────────────────────────────

def _edge_dir(edge_id: str) -> Path:
    return EDGES_DIR / edge_id


def _read_edge_info(edge_id: str) -> dict | None:
    p = _edge_dir(edge_id) / "edge_info.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _devices_key(edge_type: str) -> str:
    return "loads" if edge_type == "load" else "devices"


def read_devices(edge_id: str) -> list[dict]:
    info = _read_edge_info(edge_id)
    if info is None:
        return []
    p = _edge_dir(edge_id) / "devices.yaml"
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return raw.get(_devices_key(info["edge_type"]), [])


def write_devices(edge_id: str, devices: list[dict]) -> None:
    info = _read_edge_info(edge_id)
    p = _edge_dir(edge_id) / "devices.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw[_devices_key(info["edge_type"])] = devices
    with p.open("w", encoding="utf-8") as f:
        yaml.dump(raw, f, default_flow_style=False, allow_unicode=True)


# ── Docker helpers ───────────────────────────────────────────────────────────

def get_container_status(container_name: str) -> str:
    if not DOCKER_AVAILABLE:
        return "unknown"
    try:
        c = _docker_client.containers.get(container_name)
        return c.status  # running / exited / paused / ...
    except Exception:
        return "not_found"


def _start_container(edge_id: str, edge_type: str) -> None:
    image = EDGE_TYPE_IMAGES[edge_type]
    host_path = str(Path(HOST_EDGES_PATH) / edge_id)
    volumes = {host_path: {"bind": "/app/config", "mode": "rw"}}
    cmd = EDGE_TYPE_CMD[edge_type]
    kwargs: dict[str, Any] = dict(
        image=image,
        name=edge_id,
        detach=True,
        volumes=volumes,
        network=REAL_NETWORK_NAME,
        restart_policy={"Name": "always"},
    )
    if cmd:
        kwargs["command"] = cmd
    _docker_client.containers.run(**kwargs)


def _stop_container(edge_id: str) -> None:
    try:
        c = _docker_client.containers.get(edge_id)
        c.stop(timeout=10)
        c.remove()
    except Exception as e:
        print(f"[docker] stop/remove {edge_id}: {e}")


# ── Business logic ───────────────────────────────────────────────────────────

def list_edges() -> list[dict]:
    if not EDGES_DIR.exists():
        return []
    result = []
    for d in sorted(EDGES_DIR.iterdir()):
        if not d.is_dir():
            continue
        info = _read_edge_info(d.name)
        if info is None:
            continue
        info = dict(info)
        info["devices_count"] = len(read_devices(d.name))
        info["status"] = get_container_status(info["edge_id"])
        result.append(info)
    return result


def create_edge(body: dict) -> dict:
    edge_id = body.get("edge_id", "").strip()
    edge_type = body.get("edge_type", "").strip()
    plant_id = body.get("plant_id", "PLANT-ALPHA").strip()
    mqtt_host = body.get("mqtt_broker_host", "mqtt-broker").strip()
    mqtt_port = int(body.get("mqtt_broker_port", 1883))

    if not edge_id:
        raise ValueError("edge_id is required")
    if edge_type not in EDGE_TYPE_IMAGES:
        raise ValueError(f"edge_type must be one of: {sorted(EDGE_TYPE_IMAGES)}")
    if _edge_dir(edge_id).exists():
        raise ValueError(f"Edge '{edge_id}' already exists")

    d = _edge_dir(edge_id)
    d.mkdir(parents=True)

    info = {
        "edge_id": edge_id,
        "edge_type": edge_type,
        "plant_id": plant_id,
        "mqtt_broker_host": mqtt_host,
        "mqtt_broker_port": mqtt_port,
    }
    (d / "edge_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    if edge_type == "load":
        cfg = {
            "site_id": plant_id,
            "edge_id": edge_id,
            "mqtt_broker_host": mqtt_host,
            "mqtt_broker_port": mqtt_port,
            "publish_interval_sec": 1.0,
            "loads": [],
        }
        scenario_template = EDGES_DIR / "load-simulator" / "scenario.yaml"
        if scenario_template.exists() and edge_id != "load-simulator":
            (d / "scenario.yaml").write_bytes(scenario_template.read_bytes())
    else:
        cfg = {
            "plant_id": plant_id,
            "mqtt_broker_host": mqtt_host,
            "mqtt_broker_port": mqtt_port,
            "devices": [],
        }
    with (d / "devices.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

    if DOCKER_AVAILABLE:
        _start_container(edge_id, edge_type)

    return {"edge_id": edge_id, "status": "created"}


def delete_edge(edge_id: str) -> dict:
    edge_path = _edge_dir(edge_id)
    if not edge_path.exists():
        raise FileNotFoundError(f"Edge '{edge_id}' not found")
    
    if DOCKER_AVAILABLE:
        _stop_container(edge_id)
        
    # 설정 디렉토리 삭제
    try:
        shutil.rmtree(edge_path)
        print(f"[manager] deleted edge directory: {edge_path}")
    except Exception as e:
        print(f"[manager] failed to delete edge directory {edge_path}: {e}")
        
    return {"edge_id": edge_id, "status": "deleted"}


def add_device(edge_id: str, body: dict) -> dict:
    if not _edge_dir(edge_id).exists():
        raise FileNotFoundError(f"Edge '{edge_id}' not found")
    device_id = body.get("device_id", "").strip()
    if not device_id:
        raise ValueError("device_id is required")
    devices = read_devices(edge_id)
    if any(d.get("device_id") == device_id for d in devices):
        raise ValueError(f"Device '{device_id}' already exists")
    devices.append(body)
    write_devices(edge_id, devices)
    return {"device_id": device_id, "status": "added"}


def remove_device(edge_id: str, device_id: str) -> dict:
    if not _edge_dir(edge_id).exists():
        raise FileNotFoundError(f"Edge '{edge_id}' not found")
    devices = read_devices(edge_id)
    new_devices = [d for d in devices if d.get("device_id") != device_id]
    if len(new_devices) == len(devices):
        raise FileNotFoundError(f"Device '{device_id}' not found")
    write_devices(edge_id, new_devices)
    return {"device_id": device_id, "status": "removed"}


# ── HTTP handler ─────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log
        pass

    def log_request_line(self):
        print(f"[{self.command}] {self.path}")

    def do_GET(self):
        self.log_request_line()
        p = self.path.split("?")[0]

        if p in ("/", "/index.html"):
            return self._serve_file(STATIC_DIR / "index.html")

        if p.startswith("/static/"):
            return self._serve_file(STATIC_DIR / p[len("/static/"):])

        if p == "/api/edges":
            return _send_json(self, list_edges())

        m = re.match(r"^/api/edges/([^/]+)/devices$", p)
        if m:
            return _send_json(self, read_devices(m.group(1)))

        _send_err(self, "Not found", 404)

    def do_POST(self):
        self.log_request_line()
        p = self.path

        if p == "/api/edges":
            try:
                result = create_edge(_read_body(self))
                return _send_json(self, result, 201)
            except (ValueError, TypeError) as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        m = re.match(r"^/api/edges/([^/]+)/devices$", p)
        if m:
            try:
                result = add_device(m.group(1), _read_body(self))
                return _send_json(self, result, 201)
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except ValueError as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        _send_err(self, "Not found", 404)

    def do_DELETE(self):
        self.log_request_line()
        p = self.path

        m = re.match(r"^/api/edges/([^/]+)$", p)
        if m:
            try:
                return _send_json(self, delete_edge(m.group(1)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except Exception as e:
                return _send_err(self, str(e), 500)

        m = re.match(r"^/api/edges/([^/]+)/devices/([^/]+)$", p)
        if m:
            try:
                return _send_json(self, remove_device(m.group(1), m.group(2)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except Exception as e:
                return _send_err(self, str(e), 500)

        _send_err(self, "Not found", 404)

    def _serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return _send_err(self, "Not found", 404)
        content_type, _ = mimetypes.guess_type(str(path))
        content_type = content_type or "application/octet-stream"
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    EDGES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[simulator-manager] edges dir : {EDGES_DIR}")
    print(f"[simulator-manager] host edges: {HOST_EDGES_PATH}")
    print(f"[simulator-manager] docker    : {'available' if DOCKER_AVAILABLE else 'unavailable'}")
    print(f"[simulator-manager] listening : http://0.0.0.0:{PORT}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
