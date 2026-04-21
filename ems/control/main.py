import asyncio
import threading
from adapters.state_reader import StateReader
from adapters.mqtt_commander import MqttCommander
from adapters.db_writer import ControlDBWriter
from domain.rule_engine import run
from api import run_api
from config import CONTROL_INTERVAL_SECONDS

_pending: dict[str, str] = {}


async def main():
    reader = StateReader()
    db = ControlDBWriter()
    await db.connect()
    print(f"[control] 시작: {CONTROL_INTERVAL_SECONDS}초 주기 판단")

    try:
        async with MqttCommander(db) as commander:
            while True:
                try:
                    states = await reader.get_all()
                    if states:
                        commands = run(states)
                        sent = 0
                        for cmd in commands:
                            device_id = cmd["device_id"]
                            target_mode = cmd["payload"].get("mode") or cmd["payload"].get("command")
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
    finally:
        await db.close()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, kwargs={"port": 5001}, daemon=True)
    api_thread.start()
    print("[control] Flask API 시작: port 5001")
    asyncio.run(main())
