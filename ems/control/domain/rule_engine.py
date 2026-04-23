"""룰 오케스트레이터. 각 도메인 룰을 모아 우선순위로 충돌을 해결한다.

priority 큰 룰이 같은 device를 더 먼저 잡는다 (safety > ess > diesel).
"""

from .power_flow import compute as compute_flow
from .rules import safety, ess, diesel, solar, load


def run(states: dict, policy) -> tuple[list[dict], list[dict]]:
    """(commands, events) 튜플 반환. commands는 장치 제어, events는 이상 감지."""
    flow = compute_flow(states)

    candidates: list[dict] = []
    candidates.extend(ess.evaluate(flow, policy))
    candidates.extend(diesel.evaluate(flow, policy, states))
    candidates.extend(solar.evaluate(flow, policy, states))
    candidates.extend(load.evaluate(flow, policy, states))

    events, failsafe_commands = safety.evaluate(flow, states, policy)

    # fail-safe 명령은 priority=100으로 일반 후보보다 항상 우선
    candidates.extend(failsafe_commands)
    commands = _resolve(candidates)

    return commands, events


def _resolve(candidates: list[dict]) -> list[dict]:
    """동일 device_id에 대해 priority가 가장 높은 명령만 채택."""
    by_device: dict[str, dict] = {}
    for cmd in candidates:
        device_id = cmd["device_id"]
        existing = by_device.get(device_id)
        if existing is None or cmd.get("priority", 0) > existing.get("priority", 0):
            by_device[device_id] = cmd
    return list(by_device.values())
