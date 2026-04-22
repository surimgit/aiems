"""ESS charge/discharge/standby 룰. net_power와 SOC 임계로 모드 결정."""


PRIORITY = 50


def evaluate(flow: dict, policy) -> list[dict]:
    soc_low = policy.get("SOC_LOW")
    soc_high = policy.get("SOC_HIGH")

    ess_devices = flow["ess_devices"]
    if not ess_devices:
        return []

    # ESS는 net_power에 자기 자신도 포함되어 있어, 보정 net = 외부 net - ess_p
    external_net = flow["net_power"] - flow["ess_p"]
    commands = []

    for ess in ess_devices:
        soc = ess["SOC"]
        if soc is None:
            continue
        share = round(abs(external_net) / len(ess_devices), 1)

        if external_net < 0:
            # 외부 부족 → 방전
            if soc > soc_low and ess["mode"] != "discharge":
                commands.append(_cmd(ess, "discharge", share, external_net, soc))
        elif external_net > 0:
            # 외부 잉여 → 충전
            if soc < soc_high and ess["mode"] != "charge":
                commands.append(_cmd(ess, "charge", share, external_net, soc))
        else:
            if ess["mode"] != "standby":
                commands.append(_cmd(ess, "standby", 0.0, 0.0, soc))

    return commands


def _cmd(ess: dict, mode: str, target_kw: float, net: float, soc: float) -> dict:
    return {
        "device_id": ess["device_id"],
        "resource_type": "ess",
        "command_type": "ess_mode",
        "payload": {"mode": mode, "target_power_kw": target_kw},
        "reason": f"external_net={net:.1f}kW, SOC={soc}%",
        "priority": PRIORITY,
    }
