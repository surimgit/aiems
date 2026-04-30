"""net_power 계산. ESS P 부호 규칙(방전+, 충전-)을 그대로 적용한다."""


def compute(states: dict) -> dict:
    solar_p = 0.0
    load_p = 0.0
    ess_p = 0.0
    diesel_p = 0.0

    ess_devices = []
    diesel_devices = []

    for device_id, state in states.items():
        resource_type = state.get("resource_type", "")
        reported = state.get("reported_state", {})
        p = reported.get("P") or 0.0

        if resource_type == "SOLAR":
            solar_p += p
        elif resource_type == "LOAD":
            load_p += p
        elif resource_type == "ESS":
            ess_p += p
            ess_devices.append({
                "device_id": device_id,
                "P": p,
                "SOC": reported.get("SOC"),
                "mode": reported.get("operating_mode", "standby"),
                "power_limit_kw": reported.get("power_limit_kw"),
            })
        elif resource_type == "DIESEL":
            diesel_p += p
            diesel_devices.append({
                "device_id": device_id,
                "P": p,
                "fuel_percent": reported.get("fuel_level_percent"),
                "operating_mode": reported.get("operating_mode", ""),
                "coolant_temp": reported.get("coolant_temp"),
                "rpm": reported.get("rpm"),
            })

    # net_power: 공급 - 수요. 양수 = 잉여, 음수 = 부족.
    net_power = solar_p + diesel_p + ess_p - load_p

    return {
        "solar_p": solar_p,
        "load_p": load_p,
        "ess_p": ess_p,
        "diesel_p": diesel_p,
        "net_power": net_power,
        "ess_devices": ess_devices,
        "diesel_devices": diesel_devices,
    }
