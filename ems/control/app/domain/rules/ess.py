"""ESS charge/discharge/standby 룰. net_power와 SOC 임계로 모드 결정.

SOC 경계 진동을 막기 위해 시작 임계와 정지 임계를 분리한다(히스테리시스).
"""


PRIORITY = 50

# 충방전 전환 시 진동 방지용 SOC 여유값 (%)
SOC_HYSTERESIS = 5.0

# ESS 정격 기본값 — telemetry에 power_limit_kw 없을 때 fallback
_ESS_POWER_LIMIT_DEFAULT_KW = 50.0


def evaluate(flow: dict, policy) -> list[dict]:
    soc_low = policy.get("SOC_LOW")
    soc_high = policy.get("SOC_HIGH")
    policy_limit = policy.get("ESS_POWER_LIMIT_KW") or _ESS_POWER_LIMIT_DEFAULT_KW

    ess_devices = flow["ess_devices"]
    if not ess_devices:
        return []

    # Phase E (PLAN_TOPOLOGY_AWARE_CONTROL.md):
    # 토폴로지 고립 / wire_fault / fault 인 ESS 에는 명령 발행 안 함.
    dispatchable_ids = {e["device_id"] for e in flow.get("dispatchable_ess_devices", [])}

    # ESS는 net_power에 자기 자신도 포함되어 있어, 보정 net = 외부 net - ess_p
    external_net = flow["net_power"] - flow["ess_p"]
    commands = []

    for ess in ess_devices:
        if ess["device_id"] not in dispatchable_ids:
            # Phase E: dispatchable 이 아니면 룰 평가 스킵.
            # Phase H: 한 번씩 명시 로그 (rule_engine 디바운스 캐시와 별개로 단순 print).
            comms = ess.get("comms_health") or "unknown"
            print(f"[control][ess] skip {ess['device_id']} command: not dispatchable (comms={comms})")
            continue
        soc = ess["SOC"]
        if soc is None:
            continue
        mode = ess["mode"]

        # 장치별 정격 — telemetry에 있으면 우선, 없으면 policy 기본값
        device_limit = ess.get("power_limit_kw") or policy_limit
        raw_share = abs(external_net) / len(ess_devices)
        share = round(min(raw_share, device_limit), 1)

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
