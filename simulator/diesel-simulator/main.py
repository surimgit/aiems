import time
import os
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from core.diesel import DieselDevice
from adapters.inbound.mqtt_subscriber import DieselMQTTSubscriber
from adapters.outbound.mqtt_publisher import DieselMQTTPublisher
from adapters.outbound.heartbeat_publisher import HeartbeatPublisher

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
PLANT_ID = os.getenv("PLANT_ID", "PLANT-ALPHA")
DEVICE_ID = os.getenv("DEVICE_ID", "diesel-01")

def main():
    print(f"Starting Diesel Simulator: {DEVICE_ID} for {PLANT_ID}")
    
    # 1. Initialize Core Logic
    device = DieselDevice(PLANT_ID, DEVICE_ID, max_capacity_kw=1000.0)

    # 2. Initialize MQTT Client & Adapters
    mqtt_client = mqtt.Client()
    
    publisher = DieselMQTTPublisher(mqtt_client, PLANT_ID, DEVICE_ID)
    heartbeat_publisher = HeartbeatPublisher(mqtt_client, PLANT_ID, DEVICE_ID, "diesel")
    subscriber = DieselMQTTSubscriber(mqtt_client, PLANT_ID, DEVICE_ID)
    
    def on_command_received(payload):
        print(f"Received Command: {payload}")
        ack = device.execute_command(payload, datetime.now(timezone.utc))
        publisher.publish_ack(ack)

    subscriber.set_command_callback(on_command_received)
    
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
            
            # Update device state (디젤은 실시간 기반 시뮬레이션 우선)
            event = device.tick(real_current_time, real_current_time)
            
            # Publish Data
            if event:
                publisher.publish_event(event)
            
            telemetry = device.get_telemetry(real_current_time)
            publisher.publish_telemetry(telemetry)
            
            # Publish Heartbeat every 10 seconds
            if time.time() - last_heartbeat_time >= 10:
                heartbeat_publisher.publish()
                last_heartbeat_time = time.time()

            # 수집 주기: 1초 (디젤은 솔라보다 긴 주기로 설정 가능하나 명세 준수 필요 시 조정)
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        print("Stopping Diesel Simulator...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
