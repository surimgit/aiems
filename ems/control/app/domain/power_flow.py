"""net_power 계산. ESS P 부호 규칙(방전+, 충전-)을 그대로 적용한다.

Phase C (PLAN_TOPOLOGY_AWARE_CONTROL.md):
  flow 결과에 dispatchable_* 필드 추가.
  dispatchable = "지금 명령을 내리면 실제로 load 에 기여 가능한 자원".

  판정 기준 (Q1/Q4):
    - SOC 충분 (ESS) / 연료 OK (Diesel) — 자원별 정책
    - comms_health == 'ok' (Q4)
    - operating_mode 가 fault/error 가 아님
    - topology graph 상 적어도 하나의 LOAD 와 통전 가능

  graph 가 None 이면 토폴로지 정보 없음 → 보수적으로 모두 dispatchable=False.
"""

from __future__ import annotations

from typing import Any


def _device_comms_ok(state: dict | None) -> bool:
    if not state:
        return False
    return (state.get("comms_health") or "").lower() == "ok"


def _device_mode(state: dict | None) -> str:
    if not state:
        return ""
    return ((state.get("reported_state") or {}).get("operating_mode") or "").lower()


def _is_dispatchable_ess(ess: dict, state: dict | None, soc_low: float, graph: Any) -> bool:
    """ESS 가 지금 방전 명령을 받으면 실제 load 에 기여 가능한가."""
    soc = ess.get("SOC")
    if soc is None or soc <= soc_low:
        return False
    if not _device_comms_ok(state):
        return False
    if _device_mode(state) in ("fault", "error"):
        return False
    if graph is None:
        return False
    return graph.is_connected_to_any_load(ess["device_id"])


def _is_dispatchable_diesel(diesel: dict, state: dict | None, graph: Any) -> bool:
    """Diesel 이 지금 start 명령을 받으면 실제 load 에 기여 가능한가."""
    if not _device_comms_ok(state):
        return False
    if (diesel.get("operating_mode") or "").lower() in ("fault", "error"):
        return False
    if graph is None:
        return False
    return graph.is_connected_to_any_load(diesel["device_id"])


def compute(states: dict, *, graph: Any = None, soc_low: float = 0.0) -> dict:
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
                "comms_health": state.get("comms_health"),
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
                "comms_health": state.get("comms_health"),
            })

    # dispatchable 분리 — 명령 발행 가능한 후보만.
    dispatchable_ess_devices = [
        e for e in ess_devices
        if _is_dispatchable_ess(e, states.get(e["device_id"]), soc_low, graph)
    ]
    dispatchable_diesel_devices = [
        d for d in diesel_devices
        if _is_dispatchable_diesel(d, states.get(d["device_id"]), graph)
    ]

    isolated_resources: list[str] = []
    if graph is not None:
        # 모든 발전/저장 자원 (SOLAR/DIESEL/ESS) 에 대해 isolation 체크.
        # LOAD 는 본인이 isolated 면 다른 처리 영역 (component_deficits) 이라 제외.
        for device_id, state in states.items():
            rt = (state.get("resource_type") or "").upper()
            if rt not in ("SOLAR", "DIESEL", "ESS"):
                continue
            if graph.is_isolated(device_id):
                isolated_resources.append(device_id)

    # net_power: 공급 - 수요. 양수 = 잉여, 음수 = 부족.
    net_power = solar_p + diesel_p + ess_p - load_p

    # Phase F (PLAN_TOPOLOGY_AWARE_CONTROL.md):
    # LOAD 별 component 단위로 deficit 계산.
    # 다중 island 환경에서 각 island 별 부족분을 분리해서 보여줌.
    component_deficits = _compute_component_deficits(states, graph)

    return {
        "solar_p": solar_p,
        "load_p": load_p,
        "ess_p": ess_p,
        "diesel_p": diesel_p,
        "net_power": net_power,
        "ess_devices": ess_devices,
        "diesel_devices": diesel_devices,
        "dispatchable_ess_devices": dispatchable_ess_devices,
        "dispatchable_diesel_devices": dispatchable_diesel_devices,
        "isolated_resources": isolated_resources,
        "component_deficits": component_deficits,
    }


def _compute_component_deficits(states: dict, graph: Any) -> list[dict]:
    """LOAD 별로 reachable resource 합산하여 component 단위 deficit 산출.

    각 항목:
        {
            "load_id": str,
            "load_kw": float,
            "supply_kw": float,           # reachable solar + diesel + ess (방전 시)
            "deficit_kw": float,          # max(load_kw - supply_kw, 0)
            "reachable_resources": list[str],
        }
    graph 가 None 이면 빈 list (단일 island 가정으로 net_power 가 deficit 대체).
    """
    if graph is None:
        return []

    results: list[dict] = []
    for device_id, state in states.items():
        if (state.get("resource_type") or "").upper() != "LOAD":
            continue
        load_kw = abs((state.get("reported_state") or {}).get("P") or 0.0)

        reachable = graph.reachable_resources(device_id)
        supply_kw = 0.0
        for r_id in reachable:
            r_state = states.get(r_id)
            if not r_state:
                continue
            r_type = (r_state.get("resource_type") or "").upper()
            r_p = (r_state.get("reported_state") or {}).get("P") or 0.0
            # SOLAR / DIESEL: P > 0 만 공급, ESS: 방전 (P > 0) 시 공급으로 계산.
            if r_type in ("SOLAR", "DIESEL", "ESS") and r_p > 0:
                supply_kw += r_p

        deficit_kw = max(load_kw - supply_kw, 0.0)
        results.append({
            "load_id": device_id,
            "load_kw": round(load_kw, 2),
            "supply_kw": round(supply_kw, 2),
            "deficit_kw": round(deficit_kw, 2),
            "reachable_resources": sorted(reachable),
        })
    return results
