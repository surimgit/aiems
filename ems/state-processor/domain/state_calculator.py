from datetime import datetime, timezone


def calculate(envelope: dict) -> dict:
    resource_type = envelope.get("resource_type", "").upper()
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

    if resource_type == "ESS":
        reported_state["SOC"] = status.get("SOC")
        reported_state["operating_mode"] = status.get("operating_mode")
    elif resource_type == "LOAD":
        reported_state["demand_max"] = energy.get("demand_max")
    elif resource_type == "DIESEL":
        fuel = payload.get("fuel", {})
        engine = payload.get("engine", {})
        reported_state["fuel_level_percent"] = fuel.get("level_percent")
        reported_state["fuel_remaining_liters"] = fuel.get("remaining_liters")
        reported_state["fuel_consumption_lph"] = fuel.get("consumption_rate_lph")
        reported_state["coolant_temp"] = engine.get("coolant_temp")
        reported_state["rpm"] = engine.get("rpm")

    return {
        "site_id": envelope.get("site_id"),
        "device_id": envelope.get("resource_id"),
        "resource_type": resource_type,
        "timestamp": envelope.get("timestamp"),
        "reported_state": reported_state,
        "comms_health": status.get("comms_health", "unknown"),
        "emergency": False,
        "calculated_at": datetime.now(timezone.utc).isoformat(),
    }
