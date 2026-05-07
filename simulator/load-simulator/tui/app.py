from __future__ import annotations

import json
import os
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

from widgets.command_log import CommandLog
from widgets.command_tracker import CommandTracker
from widgets.control_panel import ControlPanel
from widgets.demand_panel import DemandPanel
from widgets.device_panel import DeviceTable
from widgets.topology_panel import TopologyPanel


class MetaHeader(Static):
    def compose(self) -> ComposeResult:
        with Horizontal(id="meta-header-container"):
            yield Label(" Plant: ", classes="meta-label")
            yield Label("", id="meta-plant", classes="meta-val")
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


class LoadTUI(App):
    CSS = """
    Screen { background: #1a1b26; }
    #meta-header-container { height: 1; background: #1f2335; padding-left: 1; border-bottom: solid #3b4261; }
    .meta-label { color: #565f89; }
    .meta-val { color: #7aa2f7; text-style: bold; }
    .meta-val-ok { color: #9ece6a; text-style: bold; }
    .meta-val-err { color: #f7768e; text-style: bold; }
    #main-layout { layout: grid; grid-size: 2 3; grid-columns: 2fr 1fr; grid-rows: auto auto 1fr; padding: 0 1; }
    #left-panel { height: 100%; }
    #right-panel { height: 100%; }
    DeviceTable { background: #24283b; border: solid cyan; margin: 1 1 0 0; padding: 1; height: auto; }
    ControlPanel { background: #24283b; border: solid yellow; margin: 1 0 0 0; padding: 1; height: auto; }
    TopologyPanel { background: #24283b; border: solid blue; margin: 1 0 0 0; padding: 1; height: auto; }
    DemandPanel { background: #24283b; border: solid orange; margin: 1 1 0 0; padding: 1; height: auto; }
    CommandTracker { background: #24283b; border: solid magenta; margin: 1 0 0 0; padding: 1; height: 100%; }
    CommandLog { background: #24283b; border: solid green; margin: 1 0 0 0; padding: 1; column-span: 2; height: 100%; }
    .stat-row { height: 1; margin-bottom: 1; }
    .stat-label { color: #7aa2f7; text-style: bold; }
    ProgressBar { width: 100%; }
    .ctrl-label { color: #7aa2f7; text-style: bold; }
    #select-row { height: 3; margin-bottom: 1; }
    #action-buttons { height: 3; margin-bottom: 1; }
    #action-buttons Button { width: 1fr; margin-right: 1; }
    #ratio-input-group { height: 3; }
    #input-shed-ratio { width: 1fr; margin-right: 1; }
    #btn-set-ratio { width: 8; }
    """

    BINDINGS = [("q", "quit", "Quit TUI")]

    def __init__(self) -> None:
        super().__init__()
        self.plant_id = os.getenv("PLANT_ID", "PLANT-ALPHA")
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            self.mqtt_client = mqtt.Client()
        self.msg_count = 0
        self.last_rate_time = time.time()
        self.device_ids: set[str] = set()
        self.topology_lines: dict = {}
        self.topology_switches: dict = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MetaHeader(id="meta-header")
        with Container(id="main-layout"):
            with Vertical(id="left-panel"):
                yield DeviceTable(id="device-table")
                yield DemandPanel(id="demand-panel")
            with Vertical(id="right-panel"):
                yield ControlPanel(id="control-panel")
                yield TopologyPanel(id="topology-panel")
                yield CommandTracker(id="command-tracker")
            yield CommandLog(id="command-log")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#meta-plant").update(self.plant_id)
        self.set_interval(1.0, self.update_msg_rate)
        self.setup_mqtt()
        self.query_one(CommandLog).log_message(f"TUI started. Connecting to {self.plant_id}...")

    def update_msg_rate(self) -> None:
        current_time = time.time()
        dt = current_time - self.last_rate_time
        if dt > 0:
            self.query_one(MetaHeader).update_rate(self.msg_count / dt)
        self.msg_count = 0
        self.last_rate_time = current_time

    def setup_mqtt(self) -> None:
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_message = self.on_message
        try:
            self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
            threading.Thread(target=self.mqtt_client.loop_forever, daemon=True).start()
        except Exception as exc:
            self.query_one(CommandLog).log_message(f"MQTT connection failed: {exc}", "error")

    def on_connect(self, client, userdata, flags, rc, properties=None) -> None:
        if rc == 0:
            client.subscribe(f"{self.plant_id}/load/+/telemetry")
            client.subscribe(f"{self.plant_id}/load/+/ack")
            client.subscribe(f"{self.plant_id}/topology/line/+")
            client.subscribe(f"{self.plant_id}/topology/switch/+")
            self.call_from_thread(self.query_one(MetaHeader).update_mqtt_status, True)
            self.call_from_thread(self.query_one(CommandLog).log_message, "Connected to MQTT broker", "success")
        else:
            self.call_from_thread(self.query_one(CommandLog).log_message, f"Connection failed (RC: {rc})", "error")

    def on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None) -> None:
        self.call_from_thread(self.query_one(MetaHeader).update_mqtt_status, False)

    def on_message(self, client, userdata, msg) -> None:
        self.msg_count += 1
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            topic_parts = topic.split("/")

            if len(topic_parts) >= 4 and topic_parts[1] == "topology":
                topo_type = topic_parts[2]
                topo_id = topic_parts[3]
                if topo_type == "line":
                    self.topology_lines[topo_id] = payload
                elif topo_type == "switch":
                    self.topology_switches[topo_id] = payload
                self.call_from_thread(self._refresh_topology)
                return

            if len(topic_parts) < 4:
                return

            device_id = topic_parts[2]

            if device_id not in self.device_ids:
                self.device_ids.add(device_id)
                self.call_from_thread(self._register_device, device_id)

            if topic.endswith("telemetry"):
                self.call_from_thread(self._handle_telemetry, device_id, payload)
            elif topic.endswith("ack"):
                cmd_id = payload.get("command_id", "unknown")
                status = payload.get("status", "unknown").upper()
                reason = payload.get("reason", "")
                log_msg = f"[{device_id}] ACK: {status}" + (f" ({reason})" if reason else "")
                level = "warning" if status == "REJECTED" else "success"
                self.call_from_thread(self.query_one(CommandLog).log_message, log_msg, level)
                self.call_from_thread(self.query_one(CommandTracker).update_status, cmd_id, status)
        except Exception:
            pass

    def _register_device(self, device_id: str) -> None:
        self.query_one("#meta-device-count").update(str(len(self.device_ids)))
        self.query_one(ControlPanel).set_device_list(sorted(self.device_ids))

    def _handle_telemetry(self, device_id: str, payload: dict) -> None:
        data = payload.get("data", {})
        self.query_one(DeviceTable).update_device(device_id, data)
        # Aggregate demand across all devices for the panel
        inst = data.get("instantaneous", {})
        energy = data.get("energy", {})
        # Store per-device values to sum across fleet
        if not hasattr(self, "_device_p"):
            self._device_p: dict[str, float] = {}
            self._device_demand_max: dict[str, float] = {}
        self._device_p[device_id] = inst.get("P", 0.0)
        self._device_demand_max[device_id] = energy.get("demand_max", 0.0)
        total_p = sum(self._device_p.values())
        total_max = sum(self._device_demand_max.values())
        self.query_one(DemandPanel).update_demand(total_p, total_max)

    def _refresh_topology(self) -> None:
        self.query_one(TopologyPanel).refresh_topology(
            self.topology_lines, self.topology_switches, self.device_ids
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        select = self.query_one("#select-device", Select)
        target = select.value
        if not target or target == Select.BLANK:
            self.query_one(CommandLog).log_message("No target device selected!", "error")
            return

        btn_id = event.button.id
        if btn_id == "btn-shed":
            self._publish_command(target, "shed", {"shed_ratio": 1.0})
        elif btn_id == "btn-restore":
            self._publish_command(target, "restore", {})
        elif btn_id == "btn-set-ratio":
            val = self.query_one("#input-shed-ratio", Input).value
            if val:
                try:
                    ratio = float(val) / 100.0
                    if not 0.0 <= ratio <= 1.0:
                        raise ValueError
                    self._publish_command(target, "shed", {"shed_ratio": ratio})
                except ValueError:
                    self.query_one(CommandLog).log_message("Invalid shed ratio (0-100)", "error")

    def _publish_command(self, device_id: str, cmd_type: str, payload: dict) -> None:
        cmd_id = f"cmd-{str(uuid.uuid4())[:8]}"
        cmd = {
            "command_id": cmd_id,
            "command_type": cmd_type,
            "payload": payload,
        }
        topic = f"{self.plant_id}/load/{device_id}/command"
        self.mqtt_client.publish(topic, json.dumps(cmd))
        self.query_one(CommandLog).log_message(f"[{device_id}] Sent: {cmd_type} {payload}")
        ratio_str = str(payload.get("shed_ratio", "-"))
        self.query_one(CommandTracker).add_command(cmd_id, cmd_type, f"{device_id} ({ratio_str})", "SENT")


if __name__ == "__main__":
    LoadTUI().run()
