import json
import time
import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1884
PLANT_ID = "PLANT-ALPHA"

def on_connect(client, userdata, flags, rc):
    print(f"✅ 테스트 클라이언트 연결 성공 (코드: {rc})")
    # 플랜트 내의 전체 토픽을 와일드카드로 수신
    client.subscribe(f"{PLANT_ID}/#")
    print(f"📡 '{PLANT_ID}/#' 토픽 구독 중...\n")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        
        if "/telemetry" in topic:
            device_id = topic.split("/")[2]
            p_val = payload.get("data", {}).get("instantaneous", {}).get("P", 0)
            state = payload.get("data", {}).get("status", {}).get("comms_health", "")
            timestamp = payload.get("timestamp", "Unknown Time")
            print(f"[{timestamp}] [📊 Telemetry] {device_id} 발전량(P): {p_val:.2f}kW | 상태: {state}")
            
        elif "/ack" in topic:
            device_id = topic.split("/")[2]
            print(f"\n[✅ Command ACK] {device_id} 응답 수신: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")
            
        elif "/heartbeat" in topic:
            device_id = payload.get('device_id', 'unknown')
            print(f"[💓 Heartbeat] {device_id} is {payload.get('status')}")
            
        elif "/event" in topic or "/emergency" in topic:
            device_id = topic.split("/")[2]
            print(f"\n[🚨 Event/Fault] {device_id} 이벤트 수신: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")
            
    except Exception as e:
        print(f"메시지 파싱 에러: {e}")

def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()

        print("=========================================")
        print("1: [solar-01] 출력 제한 (100kW)")
        print("2: [solar-02] 출력 제한 (100kW)")
        print("3: [solar-01] 출력 제한 해제")
        print("4: [solar-02] 출력 제한 해제")
        print("Ctrl+C: 종료")
        print("=========================================")

        while True:
            cmd_input = input()
            command_payload = None
            target_device = None
            cmd_id = f"cmd-{int(time.time())}"

            if cmd_input == '1':
                target_device = "solar-01"
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 100.0}
                }
            elif cmd_input == '2':
                target_device = "solar-02"
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 100.0}
                }
            elif cmd_input == '3':
                target_device = "solar-01"
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 10000.0}
                }
            elif cmd_input == '4':
                target_device = "solar-02"
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 10000.0}
                }

            if command_payload and target_device:
                cmd_topic = f"{PLANT_ID}/solar/{target_device}/command"
                print(f"\n🚀 '{target_device}'로 '{command_payload['command_type']}' 명령 전송 중...")
                client.publish(cmd_topic, json.dumps(command_payload))
            
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n테스트 종료")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
