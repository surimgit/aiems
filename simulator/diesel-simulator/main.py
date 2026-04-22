import time
import os
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from domain.device.diesel_device import DieselDevice
from adapters.inbound.mqtt_subscriber import DieselMQTTSubscriber
from adapters.outbound.mqtt_publisher import DieselMQTTPublisher
from adapters.outbound.heartbeat_publisher import HeartbeatPublisher
from domain.edge.device_manager import DeviceManager

# Configuration (In real scenario, load from yaml)
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
PLANT_ID = os.getenv("PLANT_ID", "PLANT-ALPHA")
DEVICE_IDS = os.getenv("DEVICE_IDS", "diesel-01,diesel-02").split(",")

def main():
    print(f"Starting Diesel Edge Simulator for {PLANT_ID} with devices: {DEVICE_IDS}")

    # 1. Initialize Device Manager & Load Devices
    manager = DeviceManager()
    for d_id in DEVICE_IDS:
        d_id = d_id.strip()
        if d_id:
            device = DieselDevice(PLANT_ID, d_id, max_capacity_kw=1000.0)
            manager.register_device(device)

    # 2. Initialize MQTT Client & Adapters
    mqtt_client = mqtt.Client()
    
    publisher = DieselMQTTPublisher(mqtt_client, PLANT_ID)
    heartbeat_publisher = HeartbeatPublisher(mqtt_client, PLANT_ID, "diesel")
    subscriber = DieselMQTTSubscriber(mqtt_client, PLANT_ID)
    
    def on_command_received(target_device_id: str, payload: dict):
        print(f"Received Command for {target_device_id}: {payload}")
        ack = manager.route_command(target_device_id, payload, datetime.now(timezone.utc))
        publisher.publish_ack(target_device_id, ack)

    subscriber.set_command_callback(on_command_received)

    # command 수신 자체를 EMS 통신 생존 증거로 활용 (rule-engine-spec §5.4 COMMS_TIMEOUT)
    subscriber.set_comms_alive_callback(manager.notify_comms_alive)
    
    def on_connect(client, userdata, flags, rc):
        print(f"Connected to MQTT Broker with result code {rc}")
        subscriber.subscribe()
        
    mqtt_client.on_connect = on_connect
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()

    # 3. Simulation Loop
    try:
        last_heartbeat_time = time.time()
        while True:
            real_current_time = datetime.now(timezone.utc)
            
            # Update all devices state via Manager
            telemetries, events = manager.tick_all(real_current_time)
            
            # Publish Data for all devices
            for event in events:
                publisher.publish_event(event)
            
            for telemetry in telemetries:
                publisher.publish_telemetry(telemetry)
            
            # Publish Heartbeat every 10 seconds
            if time.time() - last_heartbeat_time >= 10:
                for d_id in manager.devices.keys():
                    heartbeat_publisher.publish(d_id)
                last_heartbeat_time = time.time()

            # 수집 주기 명세 반영: 0.1초 (100ms)
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("Stopping Diesel Simulator Edge...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()

