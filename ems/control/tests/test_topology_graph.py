"""TopologyGraph 단위 테스트."""

from __future__ import annotations

import pytest

from app.domain.topology_graph import build_graph


def _topology(*, lines: list[dict], switches: list[dict], nodes: list[dict] | None = None) -> dict:
    if nodes is None:
        nodes = [
            {"node_id": "n-solar", "node_type": "GENERATION", "resource_id": "solar-01"},
            {"node_id": "n-diesel", "node_type": "GENERATION", "resource_id": "diesel-01"},
            {"node_id": "n-ess", "node_type": "STORAGE", "resource_id": "ess-01"},
            {"node_id": "n-load", "node_type": "LOAD", "resource_id": "load-01"},
        ]
    return {"site_id": "PLANT-ALPHA", "nodes": nodes, "lines": lines, "switches": switches}


def _line(line_id: str, a: str, b: str, status: str = "NORMAL") -> dict:
    return {"line_id": line_id, "from_node_id": a, "to_node_id": b, "status": status}


def _switch(switch_id: str, line_id: str, position: str = "CLOSED", *, interlock: bool = False) -> dict:
    return {
        "switch_id": switch_id, "line_id": line_id,
        "position": position, "controllable": True, "interlock_blocked": interlock,
    }


def test_empty_topology_isolates_everything():
    g = build_graph(None)
    assert g.is_isolated("solar-01") is True
    assert g.is_connected_to_any_load("solar-01") is False
    assert g.load_resource_ids == set()


def test_all_closed_full_connectivity():
    topo = _topology(
        lines=[
            _line("l-solar-ess", "n-solar", "n-ess"),
            _line("l-diesel-ess", "n-diesel", "n-ess"),
            _line("l-ess-load", "n-ess", "n-load"),
        ],
        switches=[
            _switch("sw-solar-ess", "l-solar-ess"),
            _switch("sw-diesel-ess", "l-diesel-ess"),
            _switch("sw-ess-load", "l-ess-load"),
        ],
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("solar-01") is True
    assert g.is_connected_to_any_load("diesel-01") is True
    assert g.is_connected_to_any_load("ess-01") is True
    assert g.is_isolated("solar-01") is False


def test_open_switch_breaks_path_to_load():
    # ess-load 라인의 스위치만 OPEN — solar/diesel 모두 load 와 끊김
    topo = _topology(
        lines=[
            _line("l-solar-ess", "n-solar", "n-ess"),
            _line("l-diesel-ess", "n-diesel", "n-ess"),
            _line("l-ess-load", "n-ess", "n-load"),
        ],
        switches=[
            _switch("sw-solar-ess", "l-solar-ess"),
            _switch("sw-diesel-ess", "l-diesel-ess"),
            _switch("sw-ess-load", "l-ess-load", position="OPEN"),
        ],
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("solar-01") is False
    assert g.is_connected_to_any_load("diesel-01") is False
    assert g.is_connected_to_any_load("ess-01") is False
    assert g.is_isolated("solar-01") is True


def test_only_ess_isolated_others_still_reach_load():
    # solar-load 직접 라인이 있고 ess 측만 끊긴 상황
    nodes = [
        {"node_id": "n-solar", "node_type": "GENERATION", "resource_id": "solar-01"},
        {"node_id": "n-ess", "node_type": "STORAGE", "resource_id": "ess-01"},
        {"node_id": "n-load", "node_type": "LOAD", "resource_id": "load-01"},
    ]
    topo = _topology(
        nodes=nodes,
        lines=[
            _line("l-solar-load", "n-solar", "n-load"),
            _line("l-solar-ess", "n-solar", "n-ess"),
            _line("l-ess-load", "n-ess", "n-load"),
        ],
        switches=[
            _switch("sw-solar-load", "l-solar-load"),
            _switch("sw-solar-ess", "l-solar-ess", position="OPEN"),
            _switch("sw-ess-load", "l-ess-load", position="OPEN"),
        ],
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("solar-01") is True
    # ess 양쪽 라인이 모두 OPEN → ess 는 어디로도 못 감
    assert g.is_connected_to_any_load("ess-01") is False


def test_line_status_fault_breaks_path():
    topo = _topology(
        lines=[_line("l-solar-ess", "n-solar", "n-ess", status="FAULT")],
        switches=[_switch("sw-solar-ess", "l-solar-ess")],  # 스위치 CLOSED 여도 FAULT 라인
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("solar-01") is False


def test_interlock_blocked_acts_as_open():
    topo = _topology(
        lines=[_line("l-ess-load", "n-ess", "n-load")],
        switches=[_switch("sw-ess-load", "l-ess-load", interlock=True)],
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("ess-01") is False


def test_multiple_switches_per_line_all_must_be_closed():
    # Q3: line 양 끝 차단기 2개. 하나만 OPEN 이어도 통전 불가.
    topo = _topology(
        lines=[_line("l-ess-load", "n-ess", "n-load")],
        switches=[
            _switch("sw-ess-side", "l-ess-load", position="CLOSED"),
            _switch("sw-load-side", "l-ess-load", position="OPEN"),
        ],
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("ess-01") is False


def test_resource_unknown_to_topology_is_isolated():
    g = build_graph(_topology(lines=[], switches=[]))
    assert g.is_isolated("ghost-99") is True


def test_load_to_load_reachability():
    # 두 LOAD 가 BUS 통해 연결된 경우 reachable_resources 에 다른 load 포함
    nodes = [
        {"node_id": "n-bus", "node_type": "BUS", "resource_id": None},
        {"node_id": "n-load-a", "node_type": "LOAD", "resource_id": "load-a"},
        {"node_id": "n-load-b", "node_type": "LOAD", "resource_id": "load-b"},
    ]
    topo = _topology(
        nodes=nodes,
        lines=[
            _line("l-busa", "n-bus", "n-load-a"),
            _line("l-busb", "n-bus", "n-load-b"),
        ],
        switches=[
            _switch("sw-busa", "l-busa"),
            _switch("sw-busb", "l-busb"),
        ],
    )
    g = build_graph(topo)
    # LOAD 본인도 다른 LOAD 와 연결돼있으면 connected_to_any_load=True (reachable_resources 에 load-b 포함)
    assert "load-b" in g.reachable_resources("load-a")
    assert g.is_connected_to_any_load("load-a") is True


def test_line_without_switches_is_always_energized():
    # 토폴로지 모델상 switch 없는 라인은 상시 통전 (전선만)
    topo = _topology(
        lines=[_line("l-ess-load", "n-ess", "n-load")],
        switches=[],
    )
    g = build_graph(topo)
    assert g.is_connected_to_any_load("ess-01") is True
