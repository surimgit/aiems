import json
import time
import paho.mqtt.client as mqtt

MQTT_HOST = "localhost"
MQTT_PORT = 1883
PLANT_ID = "PLANT-ALPHA"
DEVICE_ID = "solar-01"

# 구독할 토픽들
TELEMETRY_TOPIC = f"{PLANT_ID}/solar/{DEVICE_ID}/telemetry"
EVENT_TOPIC = f"{PLANT_ID}/solar/{DEVICE_ID}/event"
ACK_TOPIC = f"{PLANT_ID}/solar/{DEVICE_ID}/ack"
HEARTBEAT_TOPIC = f"{PLANT_ID}/heartbeat"

# 명령을 보낼 토픽
COMMAND_TOPIC = f"{PLANT_ID}/solar/{DEVICE_ID}/command"

def on_connect(client, userdata, flags, rc):
    print(f"✅ 테스트 클라이언트 연결 성공 (코드: {rc})")
    # 모든 관련 토픽 구독 (#은 와일드카드)
    client.subscribe(f"{PLANT_ID}/#")
    print(f"📡 '{PLANT_ID}/#' 토픽 구독 중...\n")

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        
        if topic == TELEMETRY_TOPIC:
            # 출력이 너무 많으면 주석 처리하세요
            p_val = payload.get("data", {}).get("instantaneous", {}).get("P", 0)
            state = payload.get("data", {}).get("status", {}).get("comms_health", "")
            timestamp = payload.get("timestamp", "Unknown Time")
            print(f"[{timestamp}] [📊 Telemetry] 발전량(P): {p_val:.2f}kW | 상태: {state}")
            
        elif topic == ACK_TOPIC:
            print(f"\n[✅ Command ACK] 명령 응답 수신: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")
            
        elif topic == HEARTBEAT_TOPIC:
            print(f"[💓 Heartbeat] {payload.get('device_id')} is {payload.get('status')}")
            
        elif topic == EVENT_TOPIC:
            print(f"\n[🚨 Event/Fault] 이벤트 수신: {json.dumps(payload, ensure_ascii=False, indent=2)}\n")
            
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
        print("1: 출력 제한 (Curtailment 100kW) 명령 보내기")
        print("2: 출력 제한 (Curtailment 500kW) 명령 보내기")
        print("3: 출력 제한 해제 (Curtailment 10000kW) 명령 보내기")
        print("4: 에러 리셋 (RESET) 명령 보내기")
        print("Ctrl+C: 종료")
        print("=========================================")

        while True:
            cmd_input = input()
            command_payload = None
            cmd_id = f"cmd-{int(time.time())}"

            if cmd_input == '1':
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 100.0}
                }
            elif cmd_input == '2':
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 500.0}
                }
            elif cmd_input == '3':
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "curtailment",
                    "payload": {"limit_kw": 10000.0}
                }
            elif cmd_input == '4':
                command_payload = {
                    "command_id": cmd_id,
                    "command_type": "mode_change",
                    "payload": {"action": "RESET"}
                }

            if command_payload:
                print(f"\n🚀 '{command_payload['command_type']}' 명령 전송 중...")
                client.publish(COMMAND_TOPIC, json.dumps(command_payload))
            
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n테스트 종료")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
