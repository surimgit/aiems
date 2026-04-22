"""ESS charge/discharge/standby 룰. net_power와 SOC 임계로 모드 결정.

SOC 경계 진동을 막기 위해 시작 임계와 정지 임계를 분리한다(히스테리시스).
"""


PRIORITY = 50

# 충방전 전환 시 진동 방지용 SOC 여유값 (%)
SOC_HYSTERESIS = 5.0


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
        mode = ess["mode"]
        share = round(abs(external_net) / len(ess_devices), 1)

        if external_net < 0:
            # 외부 부족 → 방전 검토
            discharge_start = soc_low + SOC_HYSTERESIS  # 새로 시작할 때 여유 필요
            if mode == "discharge":
                # 이미 방전 중이면 SOC_LOW까지 계속
                if soc <= soc_low:
                    commands.append(_cmd(ess, "standby", 0.0, external_net, soc))
            else:
                if soc > discharge_start:
                    commands.append(_cmd(ess, "discharge", share, external_net, soc))
        elif external_net > 0:
            # 외부 잉여 → 충전 검토
            charge_start = soc_high - SOC_HYSTERESIS
            if mode == "charge":
                # 이미 충전 중이면 SOC_HIGH까지 계속
                if soc >= soc_high:
                    commands.append(_cmd(ess, "standby", 0.0, external_net, soc))
            else:
                if soc < charge_start:
                    commands.append(_cmd(ess, "charge", share, external_net, soc))
        else:
            if mode != "standby":
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
