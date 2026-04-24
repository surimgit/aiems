from datetime import datetime, timezone


# SOC 임계 이하면 emergency로 판단 (control_policy의 SOC_CRITICAL_LOW 기본값)
_SOC_EMERGENCY = 5.0


_KNOWN_TYPES = {"ESS", "SOLAR", "LOAD", "DIESEL"}


def calculate(envelope: dict) -> dict:
    resource_type = envelope.get("resource_type", "").upper()
    if resource_type not in _KNOWN_TYPES:
        return None
    if not envelope.get("resource_id"):
        return None
    payload = envelope.get("payload", {})
    instantaneous = payload.get("instantaneous", {})
    status = payload.get("status", {})
    energy = payload.get("energy", {})

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

    return {
        "site_id": envelope.get("site_id"),
        "device_id": envelope.get("resource_id"),
        "resource_type": resource_type,
        "timestamp": envelope.get("timestamp"),
        "reported_state": reported_state,
        "desired_state": None,      # state_publisher에서 Redis desired 키 조회 후 채움
        "last_command_id": None,    # 위와 동일
        "comms_health": status.get("comms_health", "unknown"),
        "emergency": emergency,
        "interlock": interlock,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }
