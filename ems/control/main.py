import asyncio
from adapters.state_reader import StateReader
from adapters.mqtt_commander import MqttCommander
from domain.rule_engine import run
from config import CONTROL_INTERVAL_SECONDS

# device_id → 마지막으로 보낸 mode 기억 (ACK 없는 환경에서 중복 방지)
_pending: dict[str, str] = {}


async def main():
    reader = StateReader()
    print(f"[control] 시작: {CONTROL_INTERVAL_SECONDS}초 주기 판단")

    async with MqttCommander() as commander:
        while True:
            try:
                states = await reader.get_all()
                if states:
                    commands = run(states)
                    sent = 0
                    for cmd in commands:
                        device_id = cmd["device_id"]
                        target_mode = cmd["payload"]["mode"]
                        if _pending.get(device_id) == target_mode:
                            continue
                        await commander.send(cmd)
                        _pending[device_id] = target_mode
                        sent += 1
                    if sent == 0:
                        print(f"[control] 판단 완료: 명령 없음 (장치 {len(states)}개)")
            except Exception as e:
                print(f"[control] 오류: {e}")

            await asyncio.sleep(CONTROL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
