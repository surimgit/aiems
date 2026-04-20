from config import SOC_LOW, SOC_HIGH


def run(states: dict) -> list[dict]:
    solar_p = 0.0
    load_p = 0.0
    ess_devices = []

    for device_id, state in states.items():
        resource_type = state.get("resource_type", "")
        p = state.get("reported_state", {}).get("P") or 0.0

        if resource_type == "SOLAR":
            solar_p += p
        elif resource_type == "LOAD":
            load_p += p
        elif resource_type == "ESS":
            soc = state.get("reported_state", {}).get("SOC")
            mode = state.get("reported_state", {}).get("operating_mode", "standby")
            ess_devices.append({"device_id": device_id, "P": p, "SOC": soc, "mode": mode})

    net_power = solar_p - load_p
    commands = []

    for ess in ess_devices:
        soc = ess["SOC"]
        if soc is None:
            continue

        if net_power < 0:
            # 전력 부족 → 방전
            if soc > SOC_LOW and ess["mode"] != "discharge":
                commands.append({
                    "device_id": ess["device_id"],
                    "resource_type": "ess",
                    "command_type": "ess_mode",
                    "payload": {"mode": "discharge", "target_power_kw": round(abs(net_power) / len(ess_devices), 1)},
                    "reason": f"net_power={net_power:.1f}kW, SOC={soc}%",
                })
        elif net_power > 0:
            # 잉여 전력 → 충전
            if soc < SOC_HIGH and ess["mode"] != "charge":
                commands.append({
                    "device_id": ess["device_id"],
                    "resource_type": "ess",
                    "command_type": "ess_mode",
                    "payload": {"mode": "charge", "target_power_kw": round(net_power / len(ess_devices), 1)},
                    "reason": f"net_power={net_power:.1f}kW, SOC={soc}%",
                })
        else:
            # 균형 → 대기
            if ess["mode"] not in ("standby",):
                commands.append({
                    "device_id": ess["device_id"],
                    "resource_type": "ess",
                    "command_type": "ess_mode",
                    "payload": {"mode": "standby", "target_power_kw": 0.0},
                    "reason": "net_power balanced",
                })

    return commands
