import asyncio
import os
import time
import yaml
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from domain.device.solar_device import SolarDevice
from domain.device.interpolator import TimeSeriesInterpolator
from adapters.inbound.mqtt_subscriber import SolarMQTTSubscriber
from adapters.outbound.mqtt_publisher import SolarMQTTPublisher
from adapters.outbound.heartbeat_publisher import HeartbeatPublisher
from domain.edge.device_manager import DeviceManager

CONFIG_PATH = os.getenv("CONFIG_PATH", os.path.join(os.path.dirname(__file__), "config", "devices.yaml"))
DATA_FILE = os.getenv("DATA_FILE", "data/normalized_solar_data.jsonl")
TICK_INTERVAL = 0.1
HEARTBEAT_INTERVAL = 10
CONFIG_POLL_INTERVAL = 2


def load_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


async def watch_config(
    config_path: str,
    manager: DeviceManager,
    plant_id: str,
    interpolator: TimeSeriesInterpolator,
):
    last_mtime = os.path.getmtime(config_path)
    while True:
        await asyncio.sleep(CONFIG_POLL_INTERVAL)
        try:
            mtime = os.path.getmtime(config_path)
            if mtime == last_mtime:
                continue
            last_mtime = mtime

            config = load_config(config_path)
            new_device_ids = {d["device_id"] for d in config.get("devices", [])}
            current_ids = set(manager.devices.keys())

            for d in config.get("devices", []):
                if d["device_id"] not in current_ids:
                    device = SolarDevice(plant_id, d["device_id"], interpolator)
                    manager.register_device(device)
                    print(f"[hot-reload] Device added: {d['device_id']}")

            for device_id in current_ids - new_device_ids:
                manager.unregister_device(device_id)
                print(f"[hot-reload] Device removed: {device_id}")

        except Exception as e:
            print(f"[hot-reload] Config reload error: {e}")


async def run_simulation(
    manager: DeviceManager,
    publisher: SolarMQTTPublisher,
    heartbeat_publisher: HeartbeatPublisher,
    interpolator: TimeSeriesInterpolator,
):
    data_start_time = interpolator.get_first_time()
    if data_start_time is None:
        print("Error: No data loaded from JSONL.")
        return

    real_start_time = time.time()
    last_heartbeat_time = real_start_time

    while True:
        real_current_time = datetime.now(timezone.utc)
        elapsed = time.time() - real_start_time
        sim_datetime = datetime.fromtimestamp(data_start_time.timestamp() + elapsed, tz=timezone.utc)

        telemetries, events = manager.tick_all(sim_datetime, real_current_time)

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

    data_path = os.path.join(os.path.dirname(__file__), DATA_FILE)
    if not os.path.exists(data_path):
        data_path = "C:/ssafy/2자율프로젝트/simulator/edge_sim/data/normalized_solar_data.jsonl"

    interpolator = TimeSeriesInterpolator(data_path)

    manager = DeviceManager()
    for d in config.get("devices", []):
        device = SolarDevice(plant_id, d["device_id"], interpolator)
        manager.register_device(device)

    mqtt_client = mqtt.Client()
    publisher = SolarMQTTPublisher(mqtt_client, plant_id)
    heartbeat_publisher = HeartbeatPublisher(mqtt_client, plant_id, "solar")
    subscriber = SolarMQTTSubscriber(mqtt_client, plant_id)

    def on_command_received(target_device_id: str, payload: dict):
        print(f"Received Command for {target_device_id}: {payload}")
        ack = manager.route_command(target_device_id, payload, datetime.now(timezone.utc))
        publisher.publish_ack(target_device_id, ack)

    subscriber.set_command_callback(on_command_received)
    subscriber.set_comms_alive_callback(manager.notify_comms_alive)

    def on_connect(client, userdata, flags, rc):
        print(f"Connected to MQTT Broker with result code {rc}")
        subscriber.subscribe()

    mqtt_client.on_connect = on_connect
    # MQTT 브로커 연결 (재시도 로직 포함)
    while True:
        try:
            print(f"[SOLAR] Connecting to MQTT broker at {mqtt_host}:{mqtt_port}...")
            mqtt_client.connect(mqtt_host, mqtt_port, 60)
            break
        except Exception as e:
            print(f"[SOLAR] MQTT connection failed: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)
            
    mqtt_client.loop_start()

    print(f"Starting Solar Edge Simulator for {plant_id} with devices: {list(manager.devices.keys())}")

    try:
        await asyncio.gather(
            run_simulation(manager, publisher, heartbeat_publisher, interpolator),
            watch_config(CONFIG_PATH, manager, plant_id, interpolator),
        )
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopping Solar Simulator Edge...")
