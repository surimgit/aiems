"""power_flow.compute 의 dispatchable 분리 검증."""

from __future__ import annotations

from app.domain.power_flow import compute
from app.domain.topology_graph import build_graph


def _state(device_id: str, resource_type: str, *, P: float = 0.0, SOC: float | None = None,
           mode: str = "standby", comms: str = "ok", fuel: float | None = None) -> dict:
    return {
        "device_id": device_id,
        "resource_type": resource_type,
        "comms_health": comms,
        "reported_state": {
            "P": P,
            "SOC": SOC,
            "operating_mode": mode,
            "fuel_level_percent": fuel,
        },
    }


def _full_topology() -> dict:
    return {
        "site_id": "PLANT-ALPHA",
        "nodes": [
            {"node_id": "n-solar", "node_type": "GENERATION", "resource_id": "solar-01"},
            {"node_id": "n-diesel", "node_type": "GENERATION", "resource_id": "diesel-01"},
            {"node_id": "n-ess", "node_type": "STORAGE", "resource_id": "ess-01"},
            {"node_id": "n-load", "node_type": "LOAD", "resource_id": "load-01"},
        ],
        "lines": [
            {"line_id": "l1", "from_node_id": "n-solar", "to_node_id": "n-ess", "status": "NORMAL"},
            {"line_id": "l2", "from_node_id": "n-diesel", "to_node_id": "n-ess", "status": "NORMAL"},
            {"line_id": "l3", "from_node_id": "n-ess", "to_node_id": "n-load", "status": "NORMAL"},
        ],
        "switches": [
            {"line_id": "l1", "switch_id": "sw1", "position": "CLOSED"},
            {"line_id": "l2", "switch_id": "sw2", "position": "CLOSED"},
            {"line_id": "l3", "switch_id": "sw3", "position": "CLOSED"},
        ],
    }


def test_no_graph_means_all_non_dispatchable():
    states = {
        "ess-01": _state("ess-01", "ESS", SOC=80, mode="standby"),
        "diesel-01": _state("diesel-01", "DIESEL", mode="off"),
    }
    flow = compute(states, graph=None, soc_low=20)
    assert flow["dispatchable_ess_devices"] == []
    assert flow["dispatchable_diesel_devices"] == []


def test_full_topology_makes_resources_dispatchable():
    g = build_graph(_full_topology())
    states = {
        "solar-01": _state("solar-01", "SOLAR", P=500),
        "ess-01": _state("ess-01", "ESS", P=-50, SOC=70, mode="charge"),
        "diesel-01": _state("diesel-01", "DIESEL", P=0, mode="off", fuel=80),
        "load-01": _state("load-01", "LOAD", P=80),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert [e["device_id"] for e in flow["dispatchable_ess_devices"]] == ["ess-01"]
    assert [d["device_id"] for d in flow["dispatchable_diesel_devices"]] == ["diesel-01"]
    assert flow["isolated_resources"] == []


def test_ess_with_low_soc_not_dispatchable():
    g = build_graph(_full_topology())
    states = {
        "ess-01": _state("ess-01", "ESS", SOC=10, mode="standby"),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert flow["dispatchable_ess_devices"] == []


def test_ess_power_limit_uses_resource_spec_before_reported_state():
    states = {
        "ess-01": {
            **_state("ess-01", "ESS", SOC=80, mode="standby"),
            "resource_spec": {"power_limit_kw": 42.0},
        },
    }

    flow = compute(states, graph=None, soc_low=20)

    assert flow["ess_devices"][0]["power_limit_kw"] == 42.0


def test_ess_wire_fault_not_dispatchable_even_with_high_soc():
    # 핵심 시나리오: SOC 높지만 wire_fault → 디젤 기동을 막으면 안 됨.
    g = build_graph(_full_topology())
    states = {
        "ess-01": _state("ess-01", "ESS", SOC=80, mode="discharge", comms="wire_fault"),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert flow["dispatchable_ess_devices"] == []


def test_ess_isolated_topology_not_dispatchable():
    topo = _full_topology()
    # ess-load 라인 OPEN
    topo["switches"][2]["position"] = "OPEN"
    # ess 측 다른 라인도 끊기
    topo["switches"][0]["position"] = "OPEN"
    topo["switches"][1]["position"] = "OPEN"
    g = build_graph(topo)
    states = {
        "ess-01": _state("ess-01", "ESS", SOC=80, mode="standby"),
        "diesel-01": _state("diesel-01", "DIESEL", mode="off", fuel=80),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert flow["dispatchable_ess_devices"] == []
    # diesel 도 ess 통한 경로만 있어 isolated
    assert flow["dispatchable_diesel_devices"] == []
    assert "ess-01" in flow["isolated_resources"]


def test_isolated_resources_includes_solar():
    # solar 측 라인만 OPEN — solar 만 isolated, ESS/Diesel 은 정상.
    topo = _full_topology()
    topo["switches"][0]["position"] = "OPEN"  # sw-solar-ess
    g = build_graph(topo)
    states = {
        "solar-01": _state("solar-01", "SOLAR", P=0, comms="wire_fault"),
        "ess-01": _state("ess-01", "ESS", SOC=70, mode="charge"),
        "diesel-01": _state("diesel-01", "DIESEL", mode="off"),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert "solar-01" in flow["isolated_resources"]
    assert "ess-01" not in flow["isolated_resources"]
    assert "diesel-01" not in flow["isolated_resources"]


def test_diesel_fault_mode_not_dispatchable():
    g = build_graph(_full_topology())
    states = {
        "diesel-01": _state("diesel-01", "DIESEL", mode="fault", fuel=80),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert flow["dispatchable_diesel_devices"] == []


def test_stale_comms_not_dispatchable():
    # Q4: ok 만 dispatchable.
    g = build_graph(_full_topology())
    states = {
        "ess-01": _state("ess-01", "ESS", SOC=80, mode="standby", comms="stale"),
        "diesel-01": _state("diesel-01", "DIESEL", mode="off", fuel=80, comms="unknown"),
    }
    flow = compute(states, graph=g, soc_low=20)
    assert flow["dispatchable_ess_devices"] == []
    assert flow["dispatchable_diesel_devices"] == []


# ── Phase F: component deficit ─────────────────────────────────────────────

def test_component_deficit_single_island():
    g = build_graph(_full_topology())
    states = {
        "solar-01": _state("solar-01", "SOLAR", P=50),
        "ess-01": _state("ess-01", "ESS", P=0, SOC=70),
        "diesel-01": _state("diesel-01", "DIESEL", P=0, mode="off"),
        "load-01": _state("load-01", "LOAD", P=80),
    }
    flow = compute(states, graph=g, soc_low=20)
    deficits = flow["component_deficits"]
    assert len(deficits) == 1
    d = deficits[0]
    assert d["load_id"] == "load-01"
    assert d["load_kw"] == 80.0
    assert d["supply_kw"] == 50.0  # solar 만 P>0
    assert d["deficit_kw"] == 30.0
    assert "solar-01" in d["reachable_resources"]


def test_component_deficit_isolated_load_no_supply():
    # 모든 라인 OPEN — load 가 isolated
    topo = _full_topology()
    for sw in topo["switches"]:
        sw["position"] = "OPEN"
    g = build_graph(topo)
    states = {
        "solar-01": _state("solar-01", "SOLAR", P=500),
        "load-01": _state("load-01", "LOAD", P=80),
    }
    flow = compute(states, graph=g, soc_low=20)
    d = flow["component_deficits"][0]
    assert d["load_kw"] == 80.0
    assert d["supply_kw"] == 0.0
    assert d["deficit_kw"] == 80.0
    assert d["reachable_resources"] == []


def test_component_deficit_no_graph_returns_empty():
    states = {"load-01": _state("load-01", "LOAD", P=80)}
    flow = compute(states, graph=None)
    assert flow["component_deficits"] == []


def test_component_deficit_excludes_charging_ess():
    # ESS 가 충전 중 (P=-50) 이면 supply 에 안 들어감 (오히려 부담).
    g = build_graph(_full_topology())
    states = {
        "solar-01": _state("solar-01", "SOLAR", P=200),
        "ess-01": _state("ess-01", "ESS", P=-50, SOC=70),
        "load-01": _state("load-01", "LOAD", P=80),
    }
    flow = compute(states, graph=g, soc_low=20)
    d = flow["component_deficits"][0]
    # supply 에 ESS(-50) 는 안 들어감, solar 200 만.
    assert d["supply_kw"] == 200.0
    assert d["deficit_kw"] == 0.0  # 충분
