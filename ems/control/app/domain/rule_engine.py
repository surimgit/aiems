"""룰 오케스트레이터. 각 도메인 룰을 모아 우선순위로 충돌을 해결한다.

priority 큰 룰이 같은 device를 더 먼저 잡는다 (safety > ess > diesel).
"""

import time as _time

from .power_flow import compute as compute_flow
from .rules import safety, ess, diesel, solar, load


# Phase H: EVT-N-017 RESOURCE_ISOLATED 디바운스 (5분).
_ISOLATED_DEBOUNCE_SEC = 300.0
# device_id → 마지막 발행 monotonic time
_isolated_last_emitted: dict[str, float] = {}


def _build_isolated_events(flow: dict, states: dict) -> list[dict]:
    """isolated_resources 에 들어 있는 자원에 대해 EVT-N-017 발행 (5분 디바운스)."""
    events: list[dict] = []
    now = _time.monotonic()
    for device_id in flow.get("isolated_resources", []):
        last = _isolated_last_emitted.get(device_id, 0.0)
        if now - last < _ISOLATED_DEBOUNCE_SEC:
            continue
        _isolated_last_emitted[device_id] = now
        state = states.get(device_id, {})
        events.append({
            "_is_event": True,
            "event_type": "EVT-N-017",
            "severity": "WARNING",
            "site_id": state.get("site_id"),
            "device_id": device_id,
            "edge_id": state.get("edge_id"),
            "resource_type": state.get("resource_type"),
            "message": f"자원 토폴로지 고립: {device_id} 가 LOAD 와 통전 가능한 경로 없음",
            "payload": {
                "device_id": device_id,
                "comms_health": state.get("comms_health"),
            },
        })
    # 정상 복구된 자원은 디바운스 캐시에서 제거 (다음 고립 시 즉시 발행 가능).
    isolated_set = set(flow.get("isolated_resources", []))
    for device_id in list(_isolated_last_emitted.keys()):
        if device_id not in isolated_set:
            _isolated_last_emitted.pop(device_id, None)
    return events


async def run(states: dict, policy, event_pub, *, topology_graph=None) -> tuple[list[dict], list[dict]]:
    """(commands, events) 튜플 반환. commands는 장치 제어, events는 이상 감지.

    topology_graph 가 주어지면 dispatchability 계산에 사용. None 이면 모든 자원 isolated 취급.
    """
    soc_low = policy.get("SOC_LOW") or 0.0
    flow = compute_flow(states, graph=topology_graph, soc_low=soc_low)
    redis = event_pub._redis

    candidates: list[dict] = []
    rule_events: list[dict] = []

    for result in [
        ess.evaluate(flow, policy),
        await diesel.evaluate(flow, policy, states, redis),
        await solar.evaluate(flow, policy, states, redis),
        load.evaluate(flow, policy, states),
    ]:
        for item in result:
            if item.get("_is_event"):
                rule_events.append(item)
            else:
                candidates.append(item)

    # Phase H: 토폴로지 고립 이벤트.
    rule_events.extend(_build_isolated_events(flow, states))

    safety_events, failsafe_commands = await safety.evaluate(flow, states, policy, event_pub)

    candidates.extend(failsafe_commands)
    commands = _resolve(candidates)

    return commands, safety_events + rule_events


def _resolve(candidates: list[dict]) -> list[dict]:
    """동일 device_id에 대해 priority가 가장 높은 명령만 채택."""
    by_device: dict[str, dict] = {}
    for cmd in candidates:
        device_id = cmd["device_id"]
        existing = by_device.get(device_id)
        if existing is None or cmd.get("priority", 0) > existing.get("priority", 0):
            by_device[device_id] = cmd
    return list(by_device.values())
