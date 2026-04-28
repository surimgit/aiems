from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

import service
from config import STATIC_DIR


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


def _serve_file(handler: BaseHTTPRequestHandler, path: Path) -> None:
    if not path.exists() or not path.is_file():
        return _send_err(handler, "Not found", 404)
    content_type, _ = mimetypes.guess_type(str(path))
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", content_type or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def do_GET(self):
        p = self.path.split("?")[0]
        print(f"[GET] {p}")

        if p in ("/", "/index.html"):
            return _serve_file(self, STATIC_DIR / "index.html")
        if p.startswith("/static/"):
            return _serve_file(self, STATIC_DIR / p[len("/static/"):])
        if p == "/api/topology":
            return _send_json(self, service.get_topology())

        _send_err(self, "Not found", 404)

    def do_POST(self):
        p = self.path
        print(f"[POST] {p}")

        if p == "/api/lines":
            try:
                return _send_json(self, service.create_line(_read_body(self)), 201)
            except ValueError as e:
                return _send_err(self, str(e), 400)
            except Exception as e:
                return _send_err(self, str(e), 500)

        if p == "/api/nodes":
            try:
                return _send_json(self, service.create_node(_read_body(self)), 201)
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
                if "fault" in body:
                    return _send_json(self, service.inject_line_fault(line_id, bool(body["fault"])))
                return _send_json(self, service.update_line(line_id, body))
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
                return _send_json(self, service.update_switch(switch_id, _read_body(self)))
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
                return _send_json(self, service.delete_line(m.group(1)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except Exception as e:
                return _send_err(self, str(e), 500)

        m = re.match(r"^/api/nodes/([^/]+)$", p)
        if m:
            try:
                return _send_json(self, service.delete_node(m.group(1)))
            except FileNotFoundError as e:
                return _send_err(self, str(e), 404)
            except Exception as e:
                return _send_err(self, str(e), 500)

        _send_err(self, "Not found", 404)
