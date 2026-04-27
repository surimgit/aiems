import asyncio
import json
import os
import time
import yaml
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from domain.device.diesel_device import DieselDevice
from adapters.inbound.mqtt_subscriber import DieselMQTTSubscriber
from adapters.outbound.mqtt_publisher import DieselMQTTPublisher
from adapters.outbound.heartbeat_publisher import HeartbeatPublisher
from domain.edge.device_manager import DeviceManager

CONFIG_PATH = os.getenv("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "config", "devices.yaml"))
TICK_INTERVAL = 0.1
HEARTBEAT_INTERVAL = 10
CONFIG_POLL_INTERVAL = 2

# topology 상태 추적 (line_id → payload)
_topology_line_states: dict = {}
_topology_switch_states: dict = {}  # line_id → switch payload


def _is_wire_fault(device_id: str) -> bool:
    """디바이스에 연결된 선로 중 하나라도 차단 상태이면 True."""
    for line_id, line in _topology_line_states.items():
        if device_id not in line.get("affected_devices", []):
            continue
        if line.get("status", "NORMAL") != "NORMAL":
            return True
        sw = _topology_switch_states.get(line_id, {})
        if sw.get("position", "CLOSED") not in ("CLOSED",):
            return True
    return False


def _handle_topology_message(topic: str, payload_bytes: bytes, plant_id: str) -> None:
    try:
        payload = json.loads(payload_bytes.decode())
    except Exception:
        return
    parts = topic.split("/")
    if len(parts) < 4:
        return
    kind = parts[2]  # "line" or "switch"
    if kind == "line":
        line_id = payload.get("line_id")
        if line_id:
            _topology_line_states[line_id] = payload
    elif kind == "switch":
        line_id = payload.get("line_id")
        if line_id:
            _topology_switch_states[line_id] = payload


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


async def watch_config(config_path: str, manager: DeviceManager, plant_id: str):
    last_mtime = os.path.getmtime(config_path)
    while True:
        await asyncio.sleep(CONFIG_POLL_INTERVAL)
        try:
            mtime = os.path.getmtime(config_path)
            if mtime == last_mtime:
                continue
            last_mtime = mtime

            config = load_config(config_path)
            new_devices = {d["device_id"]: d for d in config.get("devices", [])}
            current_ids = set(manager.devices.keys())

            for device_id, d in new_devices.items():
                if device_id not in current_ids:
                    device = DieselDevice(plant_id, device_id, d.get("max_capacity_kw", 1000.0))
                    manager.register_device(device)
                    print(f"[hot-reload] Device added: {device_id}")

            for device_id in current_ids - set(new_devices.keys()):
                manager.unregister_device(device_id)
                print(f"[hot-reload] Device removed: {device_id}")

        except Exception as e:
            print(f"[hot-reload] Config reload error: {e}")


async def run_simulation(
    manager: DeviceManager,
    publisher: DieselMQTTPublisher,
    heartbeat_publisher: HeartbeatPublisher,
):
    last_heartbeat_time = time.time()

    while True:
        real_current_time = datetime.now(timezone.utc)

        # 토폴로지 wire_fault 상태 반영
        for device_id, device in manager.devices.items():
            device.wire_fault = _is_wire_fault(device_id)

        telemetries, events = manager.tick_all(real_current_time)

        for event in events:
            publisher.publish_event(event)
        for telemetry in telemetries:
            publisher.publish_telemetry(telemetry)

        if time.time() - last_heartbeat_time >= HEARTBEAT_INTERVAL:
            for d_id in list(manager.devices.keys()):
                heartbeat_publisher.publish(d_id)
            last_heartbeat_time = time.time()

        await asyncio.sleep(TICK_INTERVAL)


async def main():
    config = load_config(CONFIG_PATH)
    plant_id = config.get("plant_id", "PLANT-ALPHA")
    mqtt_host = config.get("mqtt_broker_host", os.getenv("MQTT_HOST", "localhost"))
    mqtt_port = int(config.get("mqtt_broker_port", os.getenv("MQTT_PORT", 1883)))

    manager = DeviceManager()
    for d in config.get("devices", []):
        device = DieselDevice(plant_id, d["device_id"], d.get("max_capacity_kw", 1000.0))
        manager.register_device(device)

    mqtt_client = mqtt.Client()
    publisher = DieselMQTTPublisher(mqtt_client, plant_id)
    heartbeat_publisher = HeartbeatPublisher(mqtt_client, plant_id, "diesel")
    subscriber = DieselMQTTSubscriber(mqtt_client, plant_id)

    def on_command_received(target_device_id: str, payload: dict):
        print(f"Received Command for {target_device_id}: {payload}")
        ack = manager.route_command(target_device_id, payload, datetime.now(timezone.utc))
        publisher.publish_ack(target_device_id, ack)

    subscriber.set_command_callback(on_command_received)
    subscriber.set_comms_alive_callback(manager.notify_comms_alive)

    def on_connect(client, userdata, flags, rc):
        print(f"Connected to MQTT Broker with result code {rc}")
        subscriber.subscribe()
        topology_topic = f"{plant_id}/topology/#"
        client.subscribe(topology_topic)
        print(f"[DIESEL] Subscribed to topology: {topology_topic}")

    def on_message(client, userdata, msg):
        if "/topology/" in msg.topic:
            _handle_topology_message(msg.topic, msg.payload, plant_id)

    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    # MQTT 브로커 연결 (재시도 로직 포함)
    while True:
        try:
            print(f"[DIESEL] Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
            mqtt_client.connect(mqtt_host, mqtt_port, 60)
            break
        except Exception as e:
            print(f"[DIESEL] MQTT connection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
            
    mqtt_client.loop_start()

    print(f"Starting Diesel Edge Simulator for {plant_id} with devices: {list(manager.devices.keys())}")

    try:
        await asyncio.gather(
            run_simulation(manager, publisher, heartbeat_publisher),
            watch_config(CONFIG_PATH, manager, plant_id),
        )
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping Diesel Simulator Edge...")
