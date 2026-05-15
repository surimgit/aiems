from datetime import datetime, timezone


# SOC 임계 이하면 emergency로 판단 (control_policy의 SOC_CRITICAL_LOW 기본값)
_SOC_EMERGENCY = 5.0


_KNOWN_TYPES = {"ESS", "SOLAR", "LOAD", "DIESEL", "SWITCH"}


def calculate(envelope: dict) -> dict:
    resource_type = envelope.get("resource_type", "").upper()
    if resource_type not in _KNOWN_TYPES:
        print(f"[state_calculator] 알 수 없는 resource_type 무시: {resource_type!r} | resource_id={envelope.get('resource_id')}")
        return None
    if not envelope.get("resource_id"):
        print(f"[state_calculator] resource_id 없는 envelope 무시: resource_type={resource_type}")
        return None
    payload = envelope.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    instantaneous = payload.get("instantaneous", {})
    status = payload.get("status", {})
    energy = payload.get("energy", {})
    resource_spec = _extract_resource_spec(payload)
    edge_id = envelope.get("edge_id") or envelope.get("resource_id")
    location = _extract_location(envelope, payload)

    reported_state = {
        "P": instantaneous.get("P"),
        "Q": instantaneous.get("Q"),
        "V": instantaneous.get("V"),
        "f": instantaneous.get("f"),
        "PF": instantaneous.get("PF"),
    }

    emergency = bool(envelope.get("emergency", False))
    interlock = False

    if resource_type == "ESS":
        soc = status.get("SOC")
        operating_mode = status.get("operating_mode", "")
        reported_state["SOC"] = soc
        reported_state["operating_mode"] = operating_mode

        if soc is not None and soc <= _SOC_EMERGENCY:
            emergency = True
        if operating_mode in ("fault", "error", "FAULT", "ERROR"):
            interlock = True

    elif resource_type == "LOAD":
        reported_state["demand_max"] = energy.get("demand_max")

    elif resource_type == "DIESEL":
        fuel = payload.get("fuel", {})
        engine = payload.get("engine", {})
        reported_state["operating_mode"] = status.get("operating_mode", "stopped")
        reported_state["fuel_level_percent"] = fuel.get("level_percent")
        reported_state["fuel_remaining_liters"] = fuel.get("remaining_liters")
        reported_state["fuel_consumption_lph"] = fuel.get("consumption_rate_lph")
        reported_state["coolant_temp"] = engine.get("coolant_temp")
        reported_state["rpm"] = engine.get("rpm")

        coolant = engine.get("coolant_temp")
        if coolant is not None and coolant > 95:
            emergency = True

    elif resource_type == "SWITCH":
        # SWITCH는 전기값(P/Q/V 등) 없음 — 상태 enum만 관리
        reported_state = {
            "switch_state":      status.get("switch_state", "UNKNOWN"),
            "switch_type":       status.get("switch_type", "CB"),
            "controllable":      status.get("controllable", True),
            "interlock_blocked": status.get("interlock_blocked", False),
            "last_transition_at": status.get("last_transition_at"),
        }
        if status.get("switch_state") == "FAULT":
            emergency = True
        if status.get("interlock_blocked"):
            interlock = True

    return {
        "site_id": envelope.get("site_id"),
        "edge_id": edge_id,
        "device_id": envelope.get("resource_id"),
        "resource_type": resource_type,
        "timestamp": envelope.get("timestamp"),
        "location": location,
        "latitude": location.get("latitude") if location else None,
        "longitude": location.get("longitude") if location else None,
        "reported_state": reported_state,
        "resource_spec": resource_spec,
        "telemetry_window": payload.get("window"),
        "desired_state": None,      # state_publisher에서 Redis desired 키 조회 후 채움
        "last_command_id": None,    # 위와 동일
        "comms_health": status.get("comms_health", "unknown"),
        "emergency": emergency,
        "interlock": interlock,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_resource_spec(payload: dict) -> dict:
    spec = payload.get("spec") or {}
    if not isinstance(spec, dict):
        return {}
    return {
        key: value
        for key, value in spec.items()
        if value is not None and value != ""
    }


def _extract_location(envelope: dict, payload: dict) -> dict | None:
    for source in (
        envelope,
        envelope.get("location") or {},
        payload,
        payload.get("location") or {},
        payload.get("geo") or {},
        payload.get("position") or {},
        payload.get("spec") or {},  # 시뮬레이터 spec 추가, 위도 경도 확인용
    ):
        latitude = _to_float(_first_present(source, ("latitude", "lat", "y")))
        longitude = _to_float(_first_present(source, ("longitude", "lon", "lng", "x")))
        if latitude is not None and longitude is not None:
            return {
                "latitude": latitude,
                "longitude": longitude,
            }
    return None


def _first_present(source: dict, keys: tuple[str, ...]):
    if not isinstance(source, dict):
        return None
    for key in keys:
        value = source.get(key)
        if value is not None and value != "":
            return value
    return None


def _to_float(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
