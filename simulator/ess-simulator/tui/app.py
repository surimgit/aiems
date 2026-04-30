from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, Select, Static

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from runtime_config import load_config
from widgets.command_log import CommandLog
from widgets.command_tracker import CommandTracker
from widgets.control_panel import ControlPanel
from widgets.device_panel import DevicePanel
from widgets.topology_panel import TopologyPanel


class MetaHeader(Static):
    def compose(self) -> ComposeResult:
        with Horizontal(id="meta-header-container"):
            yield Label(" Plant: ", classes="meta-label")
            yield Label("PLANT-ALPHA", id="meta-plant", classes="meta-val")
            yield Label(" | Devices: ", classes="meta-label")
            yield Label("0", id="meta-device-count", classes="meta-val")
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
    #main-layout { layout: grid; grid-size: 2 2; grid-columns: 3fr 2fr; grid-rows: 2fr 1fr; padding: 0 1; }
    #right-panel { height: 100%; }
    DevicePanel { background: #1e293b; border: solid #38bdf8; margin: 1 1 0 0; padding: 1; }
    ControlPanel { background: #1e293b; border: solid #f59e0b; margin: 1 0 0 0; padding: 1; height: auto; }
    TopologyPanel { background: #1e293b; border: solid #818cf8; margin: 1 0 0 0; padding: 1; height: auto; }
    CommandTracker { background: #1e293b; border: solid #a855f7; margin: 1 1 0 0; padding: 1; }
    CommandLog { background: #1e293b; border: solid #22c55e; margin: 1 0 0 0; padding: 1; column-span: 2; }
    .ctrl-label { color: #94a3b8; }
    #device-select-row { height: 3; margin-bottom: 1; }
    #mode-buttons { height: 3; margin-bottom: 1; }
    #mode-buttons Button { width: 1fr; margin-right: 1; }
    #power-input-group { height: 3; }
    #input-power { width: 1fr; margin-right: 1; }
    #btn-set-power { width: 8; }
    """

    def __init__(self, config_path: str | None = None) -> None:
        super().__init__()
        self.config_path = Path(config_path) if config_path else ROOT_DIR / "config" / "devices.yaml"
        self.config = load_config(self.config_path)
        self.msg_count = 0
        self.last_rate_time = time.time()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.topology_lines: dict = {}
        self.topology_switches: dict = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MetaHeader(id="meta-header")
        with Container(id="main-layout"):
            yield DevicePanel(id="device-panel")
            with Vertical(id="right-panel"):
                yield ControlPanel(id="control-panel")
                yield TopologyPanel(id="topology-panel")
            yield CommandTracker(id="command-tracker")
            yield CommandLog(id="command-log")
        yield Footer()

    def on_mount(self) -> None:
        device_ids = [device.device_id for device in self.config.devices]
        self.query_one(DevicePanel).seed_devices(device_ids)
        self.query_one(ControlPanel).seed_devices(device_ids)
        self.query_one("#meta-plant").update(self.config.plant_id)
        self.query_one("#meta-device-count").update(str(len(device_ids)))
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
            client.subscribe(f"{self.config.plant_id}/topology/line/+")
            client.subscribe(f"{self.config.plant_id}/topology/switch/+")
            self.call_from_thread(self.query_one(MetaHeader).update_mqtt_status, True)
            self.call_from_thread(self.query_one(CommandLog).log_message, "Connected to MQTT broker", "success")

    def on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None) -> None:
        self.call_from_thread(self.query_one(MetaHeader).update_mqtt_status, False)

    def on_message(self, client, userdata, msg) -> None:
        self.msg_count += 1
        payload = json.loads(msg.payload.decode())
        topic_parts = msg.topic.split("/")

        if len(topic_parts) >= 4 and topic_parts[1] == "topology":
            topo_type = topic_parts[2]
            topo_id = topic_parts[3]
            if topo_type == "line":
                self.topology_lines[topo_id] = payload
            elif topo_type == "switch":
                self.topology_switches[topo_id] = payload
            self.call_from_thread(self._refresh_topology)
            return

        if msg.topic.endswith("telemetry"):
            self.call_from_thread(self._handle_telemetry, payload)
        elif msg.topic.endswith("ack"):
            device_id = msg.topic.split("/")[2]
            cmd_id = payload.get("command_id", "unknown")
            status = payload.get("status", "unknown")
            reason = payload.get("reason", "")
            level = "warning" if status == "rejected" else "success"
            log_msg = f"{device_id} ACK {status.upper()}" + (f" ({reason})" if reason else "")
            self.call_from_thread(self.query_one(CommandLog).log_message, log_msg, level)
            self.call_from_thread(self.query_one(CommandTracker).update_status, cmd_id, status.upper())

    def _handle_telemetry(self, payload: dict) -> None:
        device_id = payload["device_id"]
        data = payload.get("data", {})
        status = data.get("status", {})
        p_val = data.get("instantaneous", {}).get("P", 0.0)
        enriched = {
            **payload,
            "state": "CHARGING" if p_val < 0 else ("DISCHARGING" if p_val > 0 else "STANDBY"),
            "temperature_c": status.get("temperature_c", 24.0),
            "data": {
                **data,
                "status": {
                    **status,
                    "state": status.get("state", "LIVE"),
                },
            },
        }
        self.query_one(DevicePanel).update_device(device_id, enriched)

    def _refresh_topology(self) -> None:
        device_ids = {d.device_id for d in self.config.devices}
        self.query_one(TopologyPanel).refresh_topology(
            self.topology_lines, self.topology_switches, device_ids
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        select = self.query_one("#select-device", Select)
        target = select.value
        if not target or target == Select.BLANK:
            self.query_one(CommandLog).log_message("No target device selected!", "error")
            return

        btn_id = event.button.id
        if btn_id == "btn-charge":
            self._publish_command(target, "charge")
        elif btn_id == "btn-discharge":
            self._publish_command(target, "discharge")
        elif btn_id == "btn-standby":
            self._publish_command(target, "standby")
        elif btn_id == "btn-set-power":
            val = self.query_one("#input-power", Input).value
            if val:
                try:
                    self._publish_command(target, None, float(val))
                except ValueError:
                    self.query_one(CommandLog).log_message("Invalid power (kW) value", "error")

    def _publish_command(self, device_id: str, mode: str | None, power_kw: float | None = None) -> None:
        cmd_id = f"cmd-{str(uuid.uuid4())[:8]}"
        payload: dict = {}
        if mode:
            payload["mode"] = mode
        if power_kw is not None:
            payload["target_power_kw"] = power_kw

        cmd = {
            "command_id": cmd_id,
            "command_type": "ess_mode",
            "payload": payload,
        }
        topic = f"{self.config.plant_id}/ess/{device_id}/command"
        self.client.publish(topic, json.dumps(cmd))

        target_str = device_id
        if mode:
            target_str += f" ({mode}" + (f" {power_kw}kW" if power_kw is not None else "") + ")"
        self.query_one(CommandLog).log_message(f"[{device_id}] Sent: ess_mode {mode or ''}")
        self.query_one(CommandTracker).add_command(cmd_id, "ess_mode", target_str, "SENT")


if __name__ == "__main__":
    EssFleetTUI().run()
