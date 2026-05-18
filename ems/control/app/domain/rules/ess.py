"""ESS charge/discharge/standby 룰. net_power와 SOC 임계로 모드 결정.

SOC 경계 진동을 막기 위해 시작 임계와 정지 임계를 분리한다(히스테리시스).
"""


PRIORITY = 50

# 충방전 전환 시 진동 방지용 SOC 여유값 (%)
SOC_HYSTERESIS = 5.0

# 0 부근에서 charge/discharge가 핑퐁하지 않도록 하는 net hold band (kW)
ESS_EXTERNAL_NET_HOLD_BAND_KW = 0.5

# ESS 정격 기본값 — telemetry에 power_limit_kw 없을 때 fallback
_ESS_POWER_LIMIT_DEFAULT_KW = 50.0


def _ess_zone_net(ess: dict, flow: dict) -> float | None:
    """이 ESS 가 연결된 load 구역들의 (supply - load) 합산.

    component_deficits 에서 이 ESS 가 reachable_resources 에 포함된 항목만.
    direct_supply_ids 에 현재 ESS 가 포함되어 있으면 자신의 방전 전력(P>0)은 제외한다.
    구역이 없으면 None (전역 fallback 사용).
    """
    ess_id = ess["device_id"]
    matched = [
        c for c in flow.get("component_deficits", [])
        if ess_id in c.get("reachable_resources", [])
    ]
    if not matched:
        return None

    own_discharge_kw = max(float(ess.get("P") or 0.0), 0.0)
    total = 0.0
    for component in matched:
        supply_kw = float(component.get("supply_kw", 0.0) or 0.0)
        direct_supply_ids = set(component.get("direct_supply_ids") or [])
        if own_discharge_kw > 0.0 and ess_id in direct_supply_ids:
            supply_kw = max(0.0, supply_kw - own_discharge_kw)
        total += supply_kw - float(component.get("load_kw", 0.0) or 0.0)
    return total


def evaluate(flow: dict, policy) -> list[dict]:
    soc_low = policy.get("SOC_LOW")
    soc_high = policy.get("SOC_HIGH")
    policy_limit = policy.get("ESS_POWER_LIMIT_KW") or _ESS_POWER_LIMIT_DEFAULT_KW

    ess_devices = flow["ess_devices"]
    if not ess_devices:
        return []

    dispatchable_ids = {e["device_id"] for e in flow.get("dispatchable_ess_devices", [])}

    # 전역 fallback net (토폴로지 없을 때)
    global_external_net = flow["net_power"] - flow["ess_p"]
    use_zone = bool(flow.get("component_deficits"))

    commands = []

    for ess in ess_devices:
        device_id = ess["device_id"]
        if device_id not in dispatchable_ids:
            comms = ess.get("comms_health") or "unknown"
            print(f"[control][ess] skip {device_id} command: not dispatchable (comms={comms})")
            continue
        soc = ess["SOC"]
        if soc is None:
            continue
        mode = ess["mode"]

        device_limit = ess.get("power_limit_kw") or policy_limit

        # 구역별 net 사용 (토폴로지 있을 때). 구역 없으면 전역 fallback.
        if use_zone:
            zone_net = _ess_zone_net(ess, flow)
            external_net = zone_net if zone_net is not None else global_external_net
        else:
            external_net = global_external_net

        # 분담량: 구역 내 dispatchable ESS 수 기준
        if use_zone:
            zone_ess_count = sum(
                1 for e in flow.get("dispatchable_ess_devices", [])
                if any(
                    e["device_id"] in c.get("reachable_resources", [])
                    for c in flow.get("component_deficits", [])
                    if device_id in c.get("reachable_resources", [])
                )
            ) or 1
            raw_share = abs(external_net) / zone_ess_count
        else:
            raw_share = abs(external_net) / len(ess_devices)

        share = round(min(raw_share, device_limit), 1)

        # 0 근처에서는 mode를 바꾸지 않고 현재 명령을 유지한다.
        if abs(external_net) < ESS_EXTERNAL_NET_HOLD_BAND_KW:
            continue

        if external_net < 0:
            discharge_start = soc_low + SOC_HYSTERESIS
            if mode == "discharge":
                if soc <= soc_low:
                    commands.append(_cmd(ess, "standby", 0.0, external_net, soc))
            else:
                if soc > discharge_start:
                    commands.append(_cmd(ess, "discharge", share, external_net, soc))
        elif external_net > 0:
            charge_start = soc_high - SOC_HYSTERESIS
            if mode == "charge":
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
        "edge_id": ess.get("edge_id"),
        "resource_type": "ess",
        "command_type": "ess_mode",
        "payload": {"mode": mode, "target_power_kw": target_kw},
        "reason": f"external_net={net:.1f}kW, SOC={soc}%",
        "priority": PRIORITY,
    }
