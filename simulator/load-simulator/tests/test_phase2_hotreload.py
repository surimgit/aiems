"""
Phase 2 Hot-reload 검증 테스트 (load-simulator)
- LoadFleet.unregister 동작
- device 추가/제거 메서드
- _watch_config: YAML 변경 시 device 추가 감지
- _watch_config: YAML 변경 시 device 제거 감지
"""
import asyncio
import os
import sys
import tempfile

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from core.load import LoadDevice, LoadDeviceConfig, LoadFleet
from simulator_app import LoadSimulatorApp, CONFIG_POLL_INTERVAL
import simulator_app as sim_app_module

sim_app_module.CONFIG_POLL_INTERVAL = 0.2  # 테스트 속도 향상


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

SITE_ID = "TEST-SITE"
EDGE_ID = "edge-01"

DEFAULT_LOAD = {
    "device_id": "load-01",
    "panel_id": "panel-01",
    "name": "office-panel",
    "rated_kw": 120.0,
    "base_kw": 80.0,
    "power_factor": 0.98,
    "voltage_v": 380.0,
    "frequency_hz": 60.0,
    "enabled": True,
    "scenario_profile": "office-day",
}

LOAD2 = {
    "device_id": "load-02",
    "panel_id": "panel-02",
    "name": "hvac-panel",
    "rated_kw": 90.0,
    "base_kw": 45.0,
    "power_factor": 0.96,
    "voltage_v": 380.0,
    "frequency_hz": 60.0,
    "enabled": True,
    "scenario_profile": "office-day",
}


def make_device_config(d: dict) -> LoadDeviceConfig:
    return LoadDeviceConfig(site_id=SITE_ID, edge_id=EDGE_ID, **d)


def make_yaml_file(loads: list) -> str:
    config = {
        "site_id": SITE_ID,
        "edge_id": EDGE_ID,
        "mqtt_broker_host": "localhost",
        "mqtt_broker_port": 1883,
        "publish_interval_sec": 1.0,
        "loads": loads,
    }
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(config, f)
    f.close()
    return f.name


def make_scenario_yaml() -> str:
    content = {
        "profiles": {
            "office-day": {"type": "constant", "factor": 1.0},
        }
    }
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(content, f)
    f.close()
    return f.name


def make_fleet(loads: list) -> LoadFleet:
    fleet = LoadFleet(site_id=SITE_ID, edge_id=EDGE_ID)
    for d in loads:
        fleet.register(LoadDevice.from_config(make_device_config(d)))
    return fleet


# ──────────────────────────────────────────────
# 테스트 1: LoadFleet.unregister
# ──────────────────────────────────────────────

def test_load_fleet_unregister():
    print("Running test_load_fleet_unregister...")

    fleet = make_fleet([DEFAULT_LOAD, LOAD2])
    assert fleet.get("load-01") is not None
    assert fleet.get("load-02") is not None

    fleet.unregister("load-01")
    assert fleet.get("load-01") is None
    assert fleet.get("load-02") is not None  # 기존 device 유지

    fleet.unregister("load-99")  # 없는 device → 에러 없이 통과
    assert len(fleet.list_all()) == 1

    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 2: panel_index 도 함께 제거되는지 확인
# ──────────────────────────────────────────────

def test_panel_index_cleaned_on_unregister():
    print("Running test_panel_index_cleaned_on_unregister...")

    fleet = make_fleet([DEFAULT_LOAD])
    assert fleet.get_by_panel_id("panel-01") is not None

    fleet.unregister("load-01")
    assert fleet.get_by_panel_id("panel-01") is None

    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 3: Hot-reload — device 추가 감지
# ──────────────────────────────────────────────

async def _hot_reload_add():
    devices_path = make_yaml_file([DEFAULT_LOAD])
    scenario_path = make_scenario_yaml()
    try:
        from runtime_config import load_config
        config = load_config(Path(devices_path), Path(scenario_path))
        app = LoadSimulatorApp.__new__(LoadSimulatorApp)
        app.config = config
        app._stop_event = asyncio.Event()

        async def inject():
            await asyncio.sleep(0.4)
            with open(devices_path, "w") as f:
                yaml.dump({
                    "site_id": SITE_ID,
                    "edge_id": EDGE_ID,
                    "mqtt_broker_host": "localhost",
                    "mqtt_broker_port": 1883,
                    "publish_interval_sec": 1.0,
                    "loads": [DEFAULT_LOAD, LOAD2],
                }, f)

        watcher = asyncio.create_task(app._watch_config())
        await inject()
        await asyncio.sleep(0.5)
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

        ids = {d.device_id for d in config.fleet.list_all()}
        assert "load-02" in ids, f"load-02 가 추가되어야 합니다. 현재: {ids}"
        assert "load-01" in ids, "load-01 은 유지되어야 합니다."
    finally:
        os.unlink(devices_path)
        os.unlink(scenario_path)


def test_hot_reload_add_device():
    print("Running test_hot_reload_add_device...")
    asyncio.run(_hot_reload_add())
    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 4: Hot-reload — device 제거 감지
# ──────────────────────────────────────────────

async def _hot_reload_remove():
    devices_path = make_yaml_file([DEFAULT_LOAD, LOAD2])
    scenario_path = make_scenario_yaml()
    try:
        from runtime_config import load_config
        config = load_config(Path(devices_path), Path(scenario_path))
        app = LoadSimulatorApp.__new__(LoadSimulatorApp)
        app.config = config
        app._stop_event = asyncio.Event()

        async def remove():
            await asyncio.sleep(0.4)
            with open(devices_path, "w") as f:
                yaml.dump({
                    "site_id": SITE_ID,
                    "edge_id": EDGE_ID,
                    "mqtt_broker_host": "localhost",
                    "mqtt_broker_port": 1883,
                    "publish_interval_sec": 1.0,
                    "loads": [DEFAULT_LOAD],
                }, f)

        watcher = asyncio.create_task(app._watch_config())
        await remove()
        await asyncio.sleep(0.5)
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

        ids = {d.device_id for d in config.fleet.list_all()}
        assert "load-02" not in ids, "load-02 가 제거되어야 합니다."
        assert "load-01" in ids, "load-01 은 유지되어야 합니다."
    finally:
        os.unlink(devices_path)
        os.unlink(scenario_path)


def test_hot_reload_remove_device():
    print("Running test_hot_reload_remove_device...")
    asyncio.run(_hot_reload_remove())
    print("  => PASSED")


# ──────────────────────────────────────────────
# 실행 진입점
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Load Phase 2 Hot-reload Tests")
    print("=" * 50)

    tests = [
        test_load_fleet_unregister,
        test_panel_index_cleaned_on_unregister,
        test_hot_reload_add_device,
        test_hot_reload_remove_device,
    ]

    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  [FAILED] {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR]  {test.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 50)
    if failed == 0:
        print("All tests passed!")
    else:
        print(f"{failed} test(s) failed.")
    sys.exit(0 if failed == 0 else 1)
