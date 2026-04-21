from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Label, Static

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_config import load_config
from widgets.command_log import CommandLog
from widgets.control_panel import ControlPanel
from widgets.device_panel import DevicePanel


class MetaHeader(Static):
    def compose(self) -> ComposeResult:
        with Horizontal(id="meta-header-container"):
            yield Label(" Plant: ", classes="meta-label")
            yield Label("PLANT-ALPHA", id="meta-plant", classes="meta-val")
            yield Label(" | MQTT: ", classes="meta-label")
            yield Label("DISCONNECTED", id="meta-mqtt", classes="meta-val-err")
            yield Label(" | Rate: ", classes="meta-label")
            yield Label("0.0 msg/s", id="meta-rate", classes="meta-val")

    def update_mqtt_status(self, is_connected: bool) -> None:
        lbl = self.query_one("#meta-mqtt")
        lbl.update("CONNECTED" if is_connected else "DISCONNECTED")
        lbl.set_classes("meta-val-ok" if is_connected else "meta-val-err")

    def update_rate(self, rate: float) -> None:
        self.query_one("#meta-rate").update(f"{rate:.1f} msg/s")


class EssFleetTUI(App):
    CSS = """
    Screen { background: #111827; }
    #meta-header-container { height: 1; background: #0f172a; padding-left: 1; border-bottom: solid #334155; }
    .meta-label { color: #94a3b8; }
    .meta-val { color: #93c5fd; text-style: bold; }
    .meta-val-ok { color: #86efac; text-style: bold; }
    .meta-val-err { color: #fca5a5; text-style: bold; }
    #main-layout { layout: grid; grid-size: 2 2; grid-columns: 3fr 2fr; grid-rows: 1fr 1fr; padding: 0 1; }
    DevicePanel { background: #1e293b; border: solid #38bdf8; margin: 1 1 0 0; padding: 1; }
    ControlPanel { background: #1e293b; border: solid #f59e0b; margin: 1 0 0 0; padding: 1; }
    CommandLog { background: #1e293b; border: solid #22c55e; margin: 1 0 0 0; padding: 1; column-span: 2; }
    """

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.config_path = Path(config_path) if config_path else ROOT_DIR / "config" / "devices.yaml"
        self.config = load_config(self.config_path)
        self.msg_count = 0
        self.last_rate_time = time.time()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MetaHeader(id="meta-header")
        with Container(id="main-layout"):
            yield DevicePanel(id="device-panel")
            yield ControlPanel(id="control-panel")
            yield CommandLog(id="command-log")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(DevicePanel).seed_devices([device.device_id for device in self.config.devices])
        self.set_interval(1.0, self.update_msg_rate)
        self.setup_mqtt()

    def update_msg_rate(self) -> None:
        current_time = time.time()
        dt = current_time - self.last_rate_time
        if dt > 0:
            self.query_one(MetaHeader).update_rate(self.msg_count / dt)
        self.msg_count = 0
        self.last_rate_time = current_time

    def setup_mqtt(self) -> None:
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        try:
            self.client.connect(self.config.mqtt_broker_host, self.config.mqtt_broker_port, 60)
            threading.Thread(target=self.client.loop_forever, daemon=True).start()
        except Exception as exc:
            self.query_one(CommandLog).log_message(f"MQTT connection failed: {exc}", "error")

    def on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        if rc == 0:
            client.subscribe(f"{self.config.plant_id}/ess/+/telemetry")
            client.subscribe(f"{self.config.plant_id}/ess/+/ack")
            self.call_from_thread(self.query_one(MetaHeader).update_mqtt_status, True)
            self.call_from_thread(self.query_one(CommandLog).log_message, "Connected to MQTT broker", "success")

    def on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None) -> None:
        self.call_from_thread(self.query_one(MetaHeader).update_mqtt_status, False)

    def on_message(self, client, userdata, msg) -> None:
        self.msg_count += 1
        payload = json.loads(msg.payload.decode())
        if msg.topic.endswith("telemetry"):
            self.call_from_thread(self._handle_telemetry, payload)
        elif msg.topic.endswith("ack"):
            device_id = msg.topic.split("/")[2]
            self.call_from_thread(
                self.query_one(CommandLog).log_message,
                f"{device_id} ACK {payload.get('status')} ({payload.get('reason', 'ok')})",
                "warning" if payload.get("status") == "rejected" else "success",
            )

    def _handle_telemetry(self, payload: dict) -> None:
        device_id = payload["device_id"]
        status = payload.get("data", {}).get("status", {})
        enriched = {
            **payload,
            "state": "CHARGING" if payload.get("data", {}).get("instantaneous", {}).get("P", 0.0) < 0 else (
                "DISCHARGING" if payload.get("data", {}).get("instantaneous", {}).get("P", 0.0) > 0 else "STANDBY"
            ),
            "temperature_c": 24.0 + abs(payload.get("data", {}).get("instantaneous", {}).get("P", 0.0)) * 0.08,
            "data": {
                **payload.get("data", {}),
                "status": {
                    **status,
                    "state": status.get("state", "LIVE"),
                },
            },
        }
        self.query_one(DevicePanel).update_device(device_id, enriched)


if __name__ == "__main__":
    EssFleetTUI().run()
