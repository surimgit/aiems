"""
Phase 1 리팩토링 검증 테스트 (diesel-simulator)
- YAML 설정 파일 로딩
- DeviceManager register / unregister
- Hot-reload: device 추가 감지
- Hot-reload: device 제거 감지
- asyncio 시뮬레이션 루프 정상 실행
"""
import asyncio
import os
import sys
import tempfile

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.device.diesel_device import DieselDevice
from domain.edge.device_manager import DeviceManager
import main as sim_main

sim_main.CONFIG_POLL_INTERVAL = 0.2  # 테스트 속도 향상을 위해 폴링 간격 단축


# ──────────────────────────────────────────────
# Fakes
# ──────────────────────────────────────────────

class FakePublisher:
    def __init__(self):
        self.events = []
        self.telemetries = []

    def publish_event(self, event):
        self.events.append(event)

    def publish_telemetry(self, telemetry):
        self.telemetries.append(telemetry)

    def publish_ack(self, device_id, ack):
        pass


class FakeHeartbeatPublisher:
    def publish(self, device_id):
        pass


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

def make_yaml_file(devices: list, plant_id: str = "TEST-PLANT") -> str:
    config = {
        "plant_id": plant_id,
        "mqtt_broker_host": "localhost",
        "mqtt_broker_port": 1883,
        "devices": devices,
    }
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(config, f)
    f.close()
    return f.name


# ──────────────────────────────────────────────
# 테스트 1: YAML 설정 파일 로딩
# ──────────────────────────────────────────────

def test_yaml_config_loading():
    print("Running test_yaml_config_loading...")

    path = make_yaml_file([
        {"device_id": "diesel-01", "max_capacity_kw": 1000.0},
        {"device_id": "diesel-02", "max_capacity_kw": 800.0},
    ])
    try:
        config = sim_main.load_config(path)
        assert config["plant_id"] == "TEST-PLANT"
        assert len(config["devices"]) == 2
        device_ids = [d["device_id"] for d in config["devices"]]
        assert "diesel-01" in device_ids
        assert "diesel-02" in device_ids
        cap = {d["device_id"]: d["max_capacity_kw"] for d in config["devices"]}
        assert cap["diesel-01"] == 1000.0
        assert cap["diesel-02"] == 800.0
    finally:
        os.unlink(path)

    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 2: DeviceManager register / unregister
# ──────────────────────────────────────────────

def test_device_manager_register_unregister():
    print("Running test_device_manager_register_unregister...")

    manager = DeviceManager()

    d1 = DieselDevice("TEST-PLANT", "diesel-01", max_capacity_kw=1000.0)
    d2 = DieselDevice("TEST-PLANT", "diesel-02", max_capacity_kw=800.0)

    manager.register_device(d1)
    manager.register_device(d2)
    assert "diesel-01" in manager.devices
    assert "diesel-02" in manager.devices

    manager.unregister_device("diesel-01")
    assert "diesel-01" not in manager.devices
    assert "diesel-02" in manager.devices  # 기존 device 유지 확인

    manager.unregister_device("diesel-99")  # 없는 device → 에러 없이 통과
    assert len(manager.devices) == 1

    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 3: Hot-reload — device 추가 감지
# ──────────────────────────────────────────────

async def _hot_reload_add():
    manager = DeviceManager()
    manager.register_device(DieselDevice("TEST-PLANT", "diesel-01", 1000.0))

    path = make_yaml_file([{"device_id": "diesel-01", "max_capacity_kw": 1000.0}])
    try:
        async def inject_new_device():
            await asyncio.sleep(0.4)
            with open(path, "w") as f:
                yaml.dump({
                    "plant_id": "TEST-PLANT",
                    "mqtt_broker_host": "localhost",
                    "mqtt_broker_port": 1883,
                    "devices": [
                        {"device_id": "diesel-01", "max_capacity_kw": 1000.0},
                        {"device_id": "diesel-02", "max_capacity_kw": 800.0},
                    ],
                }, f)

        watcher = asyncio.create_task(
            sim_main.watch_config(path, manager, "TEST-PLANT")
        )
        await inject_new_device()
        await asyncio.sleep(0.5)  # 폴링 주기(0.2s) 이상 대기
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

        assert "diesel-02" in manager.devices, \
            f"diesel-02 가 추가되어야 합니다. 현재: {list(manager.devices.keys())}"
        assert "diesel-01" in manager.devices, "diesel-01 은 유지되어야 합니다."
        assert manager.devices["diesel-02"].max_capacity_kw == 800.0, \
            "max_capacity_kw 가 올바르게 설정되어야 합니다."
    finally:
        os.unlink(path)


def test_hot_reload_add_device():
    print("Running test_hot_reload_add_device...")
    asyncio.run(_hot_reload_add())
    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 4: Hot-reload — device 제거 감지
# ──────────────────────────────────────────────

async def _hot_reload_remove():
    manager = DeviceManager()
    manager.register_device(DieselDevice("TEST-PLANT", "diesel-01", 1000.0))
    manager.register_device(DieselDevice("TEST-PLANT", "diesel-02", 800.0))

    path = make_yaml_file([
        {"device_id": "diesel-01", "max_capacity_kw": 1000.0},
        {"device_id": "diesel-02", "max_capacity_kw": 800.0},
    ])
    try:
        async def remove_device():
            await asyncio.sleep(0.4)
            with open(path, "w") as f:
                yaml.dump({
                    "plant_id": "TEST-PLANT",
                    "mqtt_broker_host": "localhost",
                    "mqtt_broker_port": 1883,
                    "devices": [{"device_id": "diesel-01", "max_capacity_kw": 1000.0}],
                }, f)

        watcher = asyncio.create_task(
            sim_main.watch_config(path, manager, "TEST-PLANT")
        )
        await remove_device()
        await asyncio.sleep(0.5)
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

        assert "diesel-02" not in manager.devices, "diesel-02 가 제거되어야 합니다."
        assert "diesel-01" in manager.devices, "diesel-01 은 유지되어야 합니다."
    finally:
        os.unlink(path)


def test_hot_reload_remove_device():
    print("Running test_hot_reload_remove_device...")
    asyncio.run(_hot_reload_remove())
    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 5: asyncio 시뮬레이션 루프 정상 실행
# ──────────────────────────────────────────────

async def _simulation_runs():
    from datetime import datetime, timezone
    manager = DeviceManager()
    manager.register_device(DieselDevice("TEST-PLANT", "diesel-01", 1000.0))

    publisher = FakePublisher()
    heartbeat = FakeHeartbeatPublisher()

    sim_task = asyncio.create_task(
        sim_main.run_simulation(manager, publisher, heartbeat)
    )
    await asyncio.sleep(0.35)  # 0.1s tick 기준 3회 이상 실행
    sim_task.cancel()
    try:
        await sim_task
    except asyncio.CancelledError:
        pass

    assert len(publisher.telemetries) >= 3, \
        f"telemetry 가 3회 이상 발행되어야 합니다. 실제: {len(publisher.telemetries)}"


def test_asyncio_simulation_runs():
    print("Running test_asyncio_simulation_runs...")
    asyncio.run(_simulation_runs())
    print("  => PASSED")


# ──────────────────────────────────────────────
# 실행 진입점
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Diesel Phase 1 Refactoring Tests")
    print("=" * 50)

    tests = [
        test_yaml_config_loading,
        test_device_manager_register_unregister,
        test_hot_reload_add_device,
        test_hot_reload_remove_device,
        test_asyncio_simulation_runs,
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
