import json
import uuid
import time
import threading
import paho.mqtt.client as mqtt
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Static, Label
from textual import work

from widgets.device_panel import DevicePanel
from widgets.control_panel import ControlPanel
from widgets.command_log import CommandLog
from widgets.command_tracker import CommandTracker

class MetaHeader(Static):
    def compose(self) -> ComposeResult:
        with Horizontal(id="meta-header-container"):
            yield Label(" Plant: ", classes="meta-label")
            yield Label("PLANT-ALPHA", id="meta-plant", classes="meta-val")
            yield Label(" | Device: ", classes="meta-label")
            yield Label("solar-01", id="meta-device", classes="meta-val")
            yield Label(" | MQTT: ", classes="meta-label")
            yield Label("DISCONNECTED", id="meta-mqtt", classes="meta-val-err")
            yield Label(" | Rate: ", classes="meta-label")
            yield Label("0.0 msg/s", id="meta-rate", classes="meta-val")

    def update_mqtt_status(self, is_connected: bool):
        lbl = self.query_one("#meta-mqtt")
        if is_connected:
            lbl.update("CONNECTED")
            lbl.set_classes("meta-val-ok")
        else:
            lbl.update("DISCONNECTED")
            lbl.set_classes("meta-val-err")

    def update_rate(self, rate: float):
        self.query_one("#meta-rate").update(f"{rate:.1f} msg/s")

class SolarTUI(App):
    """Solar Generator Simulator TUI"""
    
    CSS = """
    Screen { background: #1a1b26; }
    #meta-header-container { height: 1; background: #1f2335; padding-left: 1; border-bottom: solid #3b4261; }
    .meta-label { color: #565f89; }
    .meta-val { color: #7aa2f7; text-style: bold; }
    .meta-val-ok { color: #9ece6a; text-style: bold; }
    .meta-val-err { color: #f7768e; text-style: bold; }
    #main-layout { layout: grid; grid-size: 2 2; grid-columns: 1fr 1fr; grid-rows: 2fr 1fr; padding: 0 1; }
    #left-panel { height: 100%; }
    
    DevicePanel { background: #24283b; border: solid cyan; margin: 1 1 0 0; padding: 1; height: auto; }
    ControlPanel { background: #24283b; border: solid yellow; margin: 1 1 0 0; padding: 1; height: auto; }
    CommandTracker { background: #24283b; border: solid magenta; margin: 1 0 0 0; padding: 1; height: 100%; }
    CommandLog { background: #24283b; border: solid green; margin: 1 0 0 0; padding: 1; column-span: 2; height: 100%; }
    
    .stat-row { height: 1; margin-bottom: 1; }
    .stat-label { color: #7aa2f7; text-style: bold; }
    .stat-value { color: #c0caf5; }
    .unit { color: #565f89; margin-left: 1; }
    .alarm-normal { color: #9ece6a; text-style: bold; }
    .alarm-error { color: #f7768e; text-style: bold; }
    #power-val { color: #e0af68; }
    
    Button { width: 100%; margin-bottom: 1; }
    #curtail-input-group { height: 3; margin-top: 1; }
    #input-limit { width: 1fr; margin-right: 1; }
    #btn-set-limit { width: 10; }
    """

    BINDINGS = [
        ("r", "send_command('mode_change', {'action': 'RESET'})", "Reset Fault"),
        ("q", "quit", "Quit TUI"),
    ]

    def __init__(self, plant_id="PLANT-ALPHA", device_id="solar-01"):
        super().__init__()
        self.plant_id = plant_id
        self.device_id = device_id
        
        try:
            self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            self.mqtt_client = mqtt.Client()
            
        self.base_topic = f"{plant_id}/solar/{device_id}"
        self.cmd_topic = f"{self.base_topic}/command"
        
        self.msg_count = 0
        self.last_rate_time = time.time()
        self.current_state = "STANDBY"
        
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield MetaHeader(id="meta-header")
        with Container(id="main-layout"):
            with Vertical(id="left-panel"):
                yield DevicePanel(id="device-panel")
                yield ControlPanel(id="control-panel")
            yield CommandTracker(id="command-tracker")
            yield CommandLog(id="command-log")
        yield Footer()

    def on_mount(self) -> None:
        self.setup_mqtt()
        self.query_one("#command-log").log_message(f"TUI Started. Connecting to {self.device_id}...")
        self.set_interval(1.0, self.update_msg_rate)

    def update_msg_rate(self):
        current_time = time.time()
        dt = current_time - self.last_rate_time
        if dt > 0:
            rate = self.msg_count / dt
            self.query_one("#meta-header").update_rate(rate)
        self.msg_count = 0
        self.last_rate_time = current_time

    def setup_mqtt(self):
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_disconnect = self.on_disconnect
        self.mqtt_client.on_message = self.on_message
        
        try:
            self.mqtt_client.connect("localhost", 1884, 60)
            self.mqtt_thread = threading.Thread(target=self.mqtt_client.loop_forever, daemon=True)
            self.mqtt_thread.start()
        except Exception as e:
            self.query_one("#command-log").log_message(f"MQTT Connection Failed: {e}", "error")

    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            client.subscribe(f"{self.base_topic}/#")
            self.call_from_thread(self.query_one("#meta-header").update_mqtt_status, True)
            self.call_from_thread(self.query_one("#command-log").log_message, "Connected to MQTT Broker", "success")
        else:
            self.call_from_thread(self.query_one("#command-log").log_message, f"Connection Failed (RC: {rc})", "error")

    def on_disconnect(self, client, userdata, disconnect_flags, rc=None, properties=None):
        self.call_from_thread(self.query_one("#meta-header").update_mqtt_status, False)

    def on_message(self, client, userdata, msg):
        self.msg_count += 1
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            if topic.endswith("telemetry"):
                self.call_from_thread(self.update_telemetry, payload)
            elif topic.endswith("event"):
                # 이벤트 수신 시 상태를 FAULT 등으로 업데이트
                event_type = payload.get("event_type")
                if "FAULT" in event_type or "OVER_CURRENT" in event_type:
                    self.current_state = "FAULT"
                self.call_from_thread(self.query_one("#command-log").log_message, f"EVENT: {payload.get('message')}", "warning")
            elif topic.endswith("ack"):
                cmd_id = payload.get("command_id", "unknown")
                status = payload.get("status", "unknown").upper()
                reason = payload.get("reason", "")
                
                if status == "ACCEPTED" and self.current_state == "FAULT":
                    self.current_state = "STANDBY" # 리셋 성공 시
                
                msg_str = f"ACK: {status}" + (f" ({reason})" if reason else "")
                self.call_from_thread(self.query_one("#command-log").log_message, msg_str)
                self.call_from_thread(
                    self.query_one("#command-tracker").add_command, 
                    cmd_id, "Response", "Simulator", status
                )
        except Exception as e:
            pass

    def update_telemetry(self, payload):
        data = payload.get("data", {})
        inst = data.get("instantaneous", {})
        p_val = inst.get("P", 0.0)
        
        # FAULT 상태가 아니면 P값에 따라 GENERATING/STANDBY 결정
        if self.current_state != "FAULT":
            self.current_state = "GENERATING" if p_val > 0 else "STANDBY"
            
        self.query_one("#device-panel").update_data(self.current_state, data)

    # --- Commands ---
    def action_send_command(self, cmd_type: str, payload: dict = None):
        self.publish_command(cmd_type, payload)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-reset":
            self.publish_command("mode_change", {"action": "RESET"})
        elif event.button.id == "btn-set-limit":
            val = self.query_one("#input-limit").value
            if val:
                try:
                    self.publish_command("curtailment", {"limit_kw": float(val)})
                except ValueError:
                    self.query_one("#command-log").log_message("Invalid Limit kW", "error")

    def publish_command(self, cmd_type: str, payload: dict = None):
        cmd_id = f"cmd-{str(uuid.uuid4())[:8]}"
        cmd = {
            "command_id": cmd_id,
            "command_type": cmd_type,
            "payload": payload or {}
        }
        self.mqtt_client.publish(self.cmd_topic, json.dumps(cmd))
        
        self.query_one("#command-log").log_message(f"Sent Command: {cmd_type}")
        
        target_str = "-"
        if payload:
            target_str = str(payload.get("limit_kw", payload.get("action", "-")))
            
        self.query_one("#command-tracker").add_command(cmd_id, cmd_type.upper(), target_str, "SENT")

if __name__ == "__main__":
    app = SolarTUI()
    app.run()
