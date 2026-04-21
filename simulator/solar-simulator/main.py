import time
import os
import paho.mqtt.client as mqtt
from datetime import datetime, timezone
from core.solar import SolarDevice
from core.interpolator import TimeSeriesInterpolator
from adapters.inbound.mqtt_subscriber import SolarMQTTSubscriber
from adapters.outbound.mqtt_publisher import SolarMQTTPublisher
from adapters.outbound.heartbeat_publisher import HeartbeatPublisher

# Configuration (In real scenario, load from yaml)
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
PLANT_ID = os.getenv("PLANT_ID", "PLANT-ALPHA")
DEVICE_ID = os.getenv("DEVICE_ID", "solar-01")
DATA_FILE = os.getenv("DATA_FILE", "data/normalized_solar_data.jsonl")

def main():
    print(f"Starting Solar Simulator: {DEVICE_ID} for {PLANT_ID}")
    
    # 1. Initialize Core Logic
    # Note: data path should be adjusted based on Docker volume mapping
    data_path = os.path.join(os.path.dirname(__file__), DATA_FILE)
    if not os.path.exists(data_path):
        # fallback for local testing
        data_path = "C:/ssafy/2자율프로젝트/simulator/edge_sim/data/normalized_solar_data.jsonl"

    interpolator = TimeSeriesInterpolator(data_path)
    device = SolarDevice(PLANT_ID, DEVICE_ID, interpolator)

    # 2. Initialize MQTT Client & Adapters
    mqtt_client = mqtt.Client()
    
    publisher = SolarMQTTPublisher(mqtt_client, PLANT_ID, DEVICE_ID)
    heartbeat_publisher = HeartbeatPublisher(mqtt_client, PLANT_ID, DEVICE_ID, "solar")
    subscriber = SolarMQTTSubscriber(mqtt_client, PLANT_ID, DEVICE_ID)
    
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

    # Time-shifting setup
    data_start_time = interpolator.get_first_time()
    if data_start_time is None:
        print("Error: No data loaded from JSONL.")
        return

    real_start_time = time.time()
    time_speed_multiplier = 1 # 현실 1초당 시뮬레이션 1초 (필요시 조절)

    # 3. Simulation Loop
    try:
        while True:
            # 현실의 현재 시간(UTC)
            real_current_time = datetime.now(timezone.utc)
            
            # 데이터 재생을 위한 시뮬레이션 타임 계산
            elapsed_real_seconds = time.time() - real_start_time
            sim_time = data_start_time.timestamp() + (elapsed_real_seconds * time_speed_multiplier)
            sim_datetime = datetime.fromtimestamp(sim_time, tz=timezone.utc)
            
            # Update device state (데이터 재생은 sim_datetime 기준)
            event = device.tick(sim_datetime, real_current_time)
            
            # Publish Data
            if event:
                publisher.publish_event(event)
            
            # 텔레메트리에 시뮬레이션 시간(sim_datetime)을 담아 전송
            telemetry = device.get_telemetry(sim_datetime)
            publisher.publish_telemetry(telemetry)
            
            # Publish Heartbeat every 10 seconds (approx)
            # 0.1초 주기이므로 100번마다 한 번씩 보냄
            if int(elapsed_real_seconds * 10) % 100 == 0:
                heartbeat_publisher.publish()

            # 수집 주기 명세 반영: 0.1초 (100ms)
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("Stopping Solar Simulator...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
