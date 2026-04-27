from __future__ import annotations

import os
from pathlib import Path

PORT = int(os.environ.get("PORT", 8081))
MQTT_HOST = os.environ.get("MQTT_HOST", "mqtt-broker")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
TOPOLOGY_PATH = Path(os.environ.get("TOPOLOGY_PATH", "/app/topology.yaml"))
STATIC_DIR = Path(__file__).parent / "static"
