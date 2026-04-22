import asyncio
import threading
from adapters.state_reader import StateReader
from adapters.mqtt_commander import MqttCommander
from adapters.db_writer import ControlDBWriter
from adapters.event_publisher import EventPublisher
from adapters.policy_reader import PolicyReader
from domain.rule_engine import run
from api import run_api
from config import CONTROL_INTERVAL_SECONDS

_pending: dict[str, str] = {}


def _dedupe_key(cmd: dict) -> str:
    """같은 의미의 명령을 다시 보내지 않기 위한 키.
    ess: command_type + mode, diesel: command_type + target_kw(있으면).
    """
    payload = cmd.get("payload", {})
    parts = [cmd["command_type"]]
    if "mode" in payload:
        parts.append(str(payload["mode"]))
    if "target_kw" in payload:
        parts.append(str(payload["target_kw"]))
    return ":".join(parts)
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
    event_pub = EventPublisher()
    policy = PolicyReader()
    await db.connect()
    await event_pub.connect()
    await policy.connect()
    print(f"[control] 시작: {CONTROL_INTERVAL_SECONDS}초 주기 판단")

    refresh_task = asyncio.create_task(_refresh_policy_loop(policy))

    try:
        async with MqttCommander(db) as commander:
            while True:
                try:
                    states = await reader.get_all()
                    if states:
                        commands, events = run(states, policy)
                        sent = 0
                        for cmd in commands:
                            device_id = cmd["device_id"]
                            key = _dedupe_key(cmd)
                            if _pending.get(device_id) == key:
                                continue
                            await commander.send(cmd)
                            _pending[device_id] = key
                            sent += 1
                        if sent == 0:
                            print(f"[control] 판단 완료: 명령 없음 (장치 {len(states)}개)")
                        for evt in events:
                            await event_pub.publish(evt)
                except Exception as e:
                    print(f"[control] 오류: {e}")

                await asyncio.sleep(CONTROL_INTERVAL_SECONDS)
    finally:
        refresh_task.cancel()
        await db.close()
        await event_pub.close()
        await policy.close()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, kwargs={"port": 5001}, daemon=True)
    api_thread.start()
    print("[control] Flask API 시작: port 5001")
    asyncio.run(main())
