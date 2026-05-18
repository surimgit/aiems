from app.domain.state_calculator import calculate


def test_calculate_preserves_resource_spec_separately_from_reported_state():
    snapshot = calculate({
        "site_id": "PLANT-ALPHA",
        "edge_id": "ess-edge-01",
        "resource_id": "ess-01",
        "resource_type": "ESS",
        "timestamp": "2026-05-15T06:01:29.775331Z",
        "payload": {
            "instantaneous": {
                "P": 19.304,
                "Q": 0.0,
                "V": 380.0,
                "f": 60.0,
                "PF": 1.0,
            },
            "status": {
                "SOC": 61.423,
                "operating_mode": "discharge",
                "comms_health": "ok",
            },
            "spec": {
                "power_limit_kw": 42.0,
                "capacity_kwh": 420.0,
                "latitude": 36.35,
                "longitude": 127.38,
                "timezone": "Asia/Seoul",
            },
        },
    })

    assert snapshot["reported_state"]["P"] == 19.304
    assert "capacity_kwh" not in snapshot["reported_state"]
    assert snapshot["resource_spec"] == {
        "power_limit_kw": 42.0,
        "capacity_kwh": 420.0,
        "latitude": 36.35,
        "longitude": 127.38,
        "timezone": "Asia/Seoul",
    }
    assert snapshot["latitude"] == 36.35
    assert snapshot["longitude"] == 127.38
