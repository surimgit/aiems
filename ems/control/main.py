import asyncio
import threading
from adapters.state_reader import StateReader
from adapters.mqtt_commander import MqttCommander
from adapters.db_writer import ControlDBWriter
from adapters.policy_reader import PolicyReader
from domain.rule_engine import run
from api import run_api
from config import CONTROL_INTERVAL_SECONDS

_pending: dict[str, str] = {}
_POLICY_REFRESH_INTERVAL = 30  # seconds


async def _refresh_policy_loop(policy: PolicyReader) -> None:
    while True:
        await asyncio.sleep(_POLICY_REFRESH_INTERVAL)
        try:
            await policy.refresh()
        except Exception as e:
            print(f"[control] policy refresh 실패: {e}")


async def main():
    reader = StateReader()
    db = ControlDBWriter()
    policy = PolicyReader()
    await db.connect()
    await policy.connect()
    print(f"[control] 시작: {CONTROL_INTERVAL_SECONDS}초 주기 판단")

    refresh_task = asyncio.create_task(_refresh_policy_loop(policy))

    try:
        async with MqttCommander(db) as commander:
            while True:
                try:
                    states = await reader.get_all()
                    if states:
                        commands = run(states, policy)
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
        refresh_task.cancel()
        await db.close()
        await policy.close()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, kwargs={"port": 5001}, daemon=True)
    api_thread.start()
    print("[control] Flask API 시작: port 5001")
    asyncio.run(main())
