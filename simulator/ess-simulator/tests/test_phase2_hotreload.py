"""
Phase 2 Hot-reload 검증 테스트 (ess-simulator)
- DeviceConfig로 device 추가/제거
- _watch_config: YAML 변경 시 device 추가 감지
- _watch_config: YAML 변경 시 device 제거 감지
- 기존 device 는 영향받지 않음
"""
import asyncio
import os
import sys
import tempfile

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from runtime_config import DeviceConfig, RuntimeConfig
from simulator_app import EssSimulatorApp, CONFIG_POLL_INTERVAL
import simulator_app as sim_app_module

sim_app_module.CONFIG_POLL_INTERVAL = 0.2  # 테스트 속도 향상


# ──────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────

DEFAULT_DEVICE = {
    "device_id": "ess-01",
    "resource_type": "ess",
    "publish_interval_sec": 0.5,
    "initial_soc": 50.0,
    "power_limit_kw": 42.0,
    "capacity_kwh": 420.0,
    "low_soc_threshold": 20.0,
    "high_soc_threshold": 90.0,
    "min_safe_soc_threshold": 10.0,
    "max_safe_soc_threshold": 95.0,
    "temperature_c": 25.0,
    "max_temperature_c": 45.0,
}


def make_yaml_file(devices: list) -> str:
    config = {
        "plant_id": "TEST-PLANT",
        "mqtt_broker_host": "localhost",
        "mqtt_broker_port": 1883,
        "devices": devices,
    }
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.dump(config, f)
    f.close()
    return f.name


def make_runtime_config(devices: list) -> RuntimeConfig:
    return RuntimeConfig(
        plant_id="TEST-PLANT",
        mqtt_broker_host="localhost",
        mqtt_broker_port=1883,
        devices=[DeviceConfig(**d) for d in devices],
    )


def make_app(devices: list, config_path: str) -> EssSimulatorApp:
    config = make_runtime_config(devices)
    app = EssSimulatorApp.__new__(EssSimulatorApp)
    app.config = config
    app.config_path = Path(config_path)
    app.simulators = {}
    app.command_handlers = {}
    app._stop_event = asyncio.Event()
    for d in config.devices:
        app.add_device(d)
    return app


# ──────────────────────────────────────────────
# 테스트 1: add_device / remove_device
# ──────────────────────────────────────────────

def test_add_remove_device():
    print("Running test_add_remove_device...")

    path = make_yaml_file([DEFAULT_DEVICE])
    try:
        app = make_app([DEFAULT_DEVICE], path)
        assert "ess-01" in app.simulators

        d2 = {**DEFAULT_DEVICE, "device_id": "ess-02", "initial_soc": 60.0}
        app.add_device(DeviceConfig(**d2))
        assert "ess-02" in app.simulators
        assert "ess-01" in app.simulators  # 기존 device 유지

        app.remove_device("ess-01")
        assert "ess-01" not in app.simulators
        assert "ess-02" in app.simulators  # 나머지 유지

        app.remove_device("ess-99")  # 없는 device → 에러 없이 통과
    finally:
        os.unlink(path)

    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 2: add_device 중복 호출 무시
# ──────────────────────────────────────────────

def test_add_device_duplicate_ignored():
    print("Running test_add_device_duplicate_ignored...")

    path = make_yaml_file([DEFAULT_DEVICE])
    try:
        app = make_app([DEFAULT_DEVICE], path)
        assert len(app.simulators) == 1

        app.add_device(DeviceConfig(**DEFAULT_DEVICE))  # 중복 추가
        assert len(app.simulators) == 1  # 여전히 1개여야 함
    finally:
        os.unlink(path)

    print("  => PASSED")


# ──────────────────────────────────────────────
# 테스트 3: Hot-reload — device 추가 감지
# ──────────────────────────────────────────────

async def _hot_reload_add():
    path = make_yaml_file([DEFAULT_DEVICE])
    try:
        app = make_app([DEFAULT_DEVICE], path)

        async def inject():
            await asyncio.sleep(0.4)
            d2 = {**DEFAULT_DEVICE, "device_id": "ess-02", "initial_soc": 60.0}
            with open(path, "w") as f:
                yaml.dump({
                    "plant_id": "TEST-PLANT",
                    "mqtt_broker_host": "localhost",
                    "mqtt_broker_port": 1883,
                    "devices": [DEFAULT_DEVICE, d2],
                }, f)

        watcher = asyncio.create_task(app._watch_config())
        await inject()
        await asyncio.sleep(0.5)
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

        assert "ess-02" in app.simulators, \
            f"ess-02 가 추가되어야 합니다. 현재: {list(app.simulators.keys())}"
        assert "ess-01" in app.simulators, "ess-01 은 유지되어야 합니다."
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
    d2 = {**DEFAULT_DEVICE, "device_id": "ess-02", "initial_soc": 60.0}
    path = make_yaml_file([DEFAULT_DEVICE, d2])
    try:
        app = make_app([DEFAULT_DEVICE, d2], path)

        async def remove():
            await asyncio.sleep(0.4)
            with open(path, "w") as f:
                yaml.dump({
                    "plant_id": "TEST-PLANT",
                    "mqtt_broker_host": "localhost",
                    "mqtt_broker_port": 1883,
                    "devices": [DEFAULT_DEVICE],
                }, f)

        watcher = asyncio.create_task(app._watch_config())
        await remove()
        await asyncio.sleep(0.5)
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass

        assert "ess-02" not in app.simulators, "ess-02 가 제거되어야 합니다."
        assert "ess-01" in app.simulators, "ess-01 은 유지되어야 합니다."
    finally:
        os.unlink(path)


def test_hot_reload_remove_device():
    print("Running test_hot_reload_remove_device...")
    asyncio.run(_hot_reload_remove())
    print("  => PASSED")


# ──────────────────────────────────────────────
# 실행 진입점
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("ESS Phase 2 Hot-reload Tests")
    print("=" * 50)

    tests = [
        test_add_remove_device,
        test_add_device_duplicate_ignored,
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
