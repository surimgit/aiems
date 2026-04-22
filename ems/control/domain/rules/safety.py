"""이상 감지 룰. 명령이 아닌 이벤트를 반환한다.

설계문서 §4.6 기준. 감지된 이상은 EventPublisher가 Redis stream에 발행한다.
"""

from datetime import datetime, timezone

PRIORITY = 100

# 이미 발행된 알람 키 추적 — 상태 회복 시 제거
_alerted: set[str] = set()

# net_power 부족 연속 감지 카운터 (모듈 레벨 — 프로세스 재시작 시 초기화)
_deficit_count: int = 0
_DEFICIT_THRESHOLD = 3      # 연속 N회
_DEFICIT_KW = -50.0         # 기준값 kW


def evaluate(flow: dict, states: dict, policy) -> list[dict]:
    global _deficit_count

    events = []
    now = datetime.now(timezone.utc)

    soc_low = policy.get("SOC_LOW")
    soc_critical = policy.get("SOC_CRITICAL_LOW")
    fuel_low = policy.get("DIESEL_FUEL_LOW")
    fuel_critical = policy.get("DIESEL_FUEL_CRITICAL")
    state_ttl = policy.get("STATE_TTL")

    # ESS 이상 감지
    for ess in flow["ess_devices"]:
        soc = ess["SOC"]
        if soc is None:
            continue
        device_id = ess["device_id"]

        if soc <= soc_critical:
            key = f"{device_id}:EVT-E-001"
            if key not in _alerted:
                _alerted.add(key)
                events.append(_evt(
                    device_id, "ess", "EVT-E-001", "CRITICAL",
                    f"ESS SOC 긴급 하한 도달: {soc}% <= {soc_critical}%",
                    {"SOC": soc},
                ))
        else:
            _alerted.discard(f"{device_id}:EVT-E-001")

        if soc_critical < soc <= soc_low:
            key = f"{device_id}:EVT-N-001"
            if key not in _alerted:
                _alerted.add(key)
                events.append(_evt(
                    device_id, "ess", "EVT-N-001", "WARNING",
                    f"ESS SOC 하한 경고: {soc}% <= {soc_low}%",
                    {"SOC": soc},
                ))
        else:
            _alerted.discard(f"{device_id}:EVT-N-001")

    # Diesel 연료 이상 감지
    for diesel in flow["diesel_devices"]:
        fuel = diesel["fuel_percent"]
        if fuel is None:
            continue
        device_id = diesel["device_id"]

        if fuel <= fuel_critical:
            key = f"{device_id}:EVT-E-002"
            if key not in _alerted:
                _alerted.add(key)
                events.append(_evt(
                    device_id, "diesel", "EVT-E-002", "CRITICAL",
                    f"디젤 연료 긴급 하한 도달: {fuel}% <= {fuel_critical}%",
                    {"fuel_percent": fuel},
                ))
        else:
            _alerted.discard(f"{device_id}:EVT-E-002")

        if fuel_critical < fuel <= fuel_low:
            key = f"{device_id}:EVT-N-002"
            if key not in _alerted:
                _alerted.add(key)
                events.append(_evt(
                    device_id, "diesel", "EVT-N-002", "WARNING",
                    f"디젤 연료 부족 경고: {fuel}% <= {fuel_low}%",
                    {"fuel_percent": fuel},
                ))
        else:
            _alerted.discard(f"{device_id}:EVT-N-002")

    # net_power 연속 부족 감지
    if flow["net_power"] < _DEFICIT_KW:
        _deficit_count += 1
    else:
        _deficit_count = 0

    if _deficit_count >= _DEFICIT_THRESHOLD:
        key = "system:EVT-N-003"
        if key not in _alerted:
            _alerted.add(key)
            events.append(_evt(
                "system", "system", "EVT-N-003", "WARNING",
                f"전력 부족 {_DEFICIT_THRESHOLD}회 연속: net={flow['net_power']:.1f}kW",
                {"net_power": flow["net_power"], "count": _deficit_count},
            ))
    else:
        _alerted.discard("system:EVT-N-003")

    # STATE_TTL 초과 디바이스 감지
    if state_ttl:
        for device_id, state in states.items():
            calculated_at = state.get("calculated_at")
            if not calculated_at:
                continue
            try:
                ts = datetime.fromisoformat(calculated_at)
                age = (now - ts).total_seconds()
                key = f"{device_id}:EVT-N-004"
                if age > state_ttl:
                    if key not in _alerted:
                        _alerted.add(key)
                        events.append(_evt(
                            device_id,
                            state.get("resource_type", "unknown").lower(),
                            "EVT-N-004", "WARNING",
                            f"STATE_TTL 초과: {device_id} 마지막 갱신 {age:.0f}초 전",
                            {"age_seconds": round(age)},
                        ))
                else:
                    _alerted.discard(key)
            except Exception:
                continue

    return events


def _evt(device_id: str, resource_type: str, event_type: str,
         severity: str, message: str, payload: dict) -> dict:
    return {
        "device_id": device_id,
        "resource_type": resource_type,
        "event_type": event_type,
        "severity": severity,
        "message": message,
        "payload": payload,
    }
