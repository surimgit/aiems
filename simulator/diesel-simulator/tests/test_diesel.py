import os
import sys
from datetime import datetime, timedelta, timezone

# 현재 파일의 상위 디렉토리(diesel-simulator)를 sys.path에 추가하여 core 패키지를 찾을 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.diesel import DieselDevice
from core.models import DeviceState

def get_diesel_device():
    """테스트용 DieselDevice 인스턴스 생성 (기존 fixture 대체)"""
    return DieselDevice(plant_id="TEST-PLANT", device_id="diesel-test", max_capacity_kw=1000.0)

def is_approx(a, b, rel_tol=1e-6):
    """pytest.approx 기능을 대체하는 근사치 비교 함수"""
    return abs(a - b) <= rel_tol * max(abs(a), abs(b))

def test_initial_state():
    """초기 상태 검증"""
    print("Running test_initial_state...")
    device = get_diesel_device()
    assert device.state == DeviceState.OFF
    assert device.data.instantaneous.P == 0.0
    assert device.current_fuel_l == 1500.0
    print("  => Success")

def test_start_command_and_transition():
    """START 명령 후 STARTING -> RUNNING 상태 전이 검증"""
    print("Running test_start_command_and_transition...")
    device = get_diesel_device()
    now = datetime.now(timezone.utc)
    
    # 1. Start 명령 실행
    ack = device.execute_command({"command_id": "c1", "command_type": "start"}, now)
    assert ack.status == "accepted"
    assert device.state == DeviceState.STARTING
    
    # 2. tick 실행 (시간 경과 전)
    device.tick(now, now)
    assert device.state == DeviceState.STARTING
    
    # 3. Startup 시간(10초) 경과 후 tick 실행
    future = now + timedelta(seconds=11)
    event = device.tick(future, future)
    
    assert device.state == DeviceState.RUNNING
    assert event is not None
    assert event.event_type == "STATE_CHANGED"
    print("  => Success")

def test_load_control_and_fuel_consumption():
    """부하 제어 및 연료 소모 로직 검증"""
    print("Running test_load_control_and_fuel_consumption...")
    device = get_diesel_device()
    now = datetime.now(timezone.utc)
    
    # 1. 가동 상태로 진입 (강제 설정)
    device.state = DeviceState.RUNNING
    device.state_start_time = now
    device.last_update_time = now
    
    # 2. 부하 설정 (500kW)
    device.execute_command({
        "command_id": "c2", 
        "command_type": "load_control", 
        "payload": {"target_kw": 500.0}
    }, now)
    
    # 3. 1시간(3600초) 경과 시뮬레이션
    future = now + timedelta(hours=1)
    device.tick(future, future)
    
    # 발전량 확인: 500kW * 1h = 500kWh
    assert is_approx(device.data.energy.kWh, 500.0)
    
    # 연료 소모 확인: (500kW * 0.25) + 5.0 (idle) = 130 L/h
    # 1500L - 130L = 1370L
    assert is_approx(device.current_fuel_l, 1370.0)
    assert device.data.fuel.remaining_liters == 1370.0
    print("  => Success")

def test_stop_command():
    """STOP 명령 및 상태 전이 검증"""
    print("Running test_stop_command...")
    device = get_diesel_device()
    now = datetime.now(timezone.utc)
    device.state = DeviceState.RUNNING
    device.state_start_time = now
    device.last_update_time = now
    
    # 1. Stop 명령
    ack = device.execute_command({"command_id": "c3", "command_type": "stop"}, now)
    assert ack.status == "accepted"
    assert device.state == DeviceState.STOPPING
    
    # 2. Shutdown 시간(5초) 경과 후
    future = now + timedelta(seconds=6)
    device.tick(future, future)
    assert device.state == DeviceState.OFF
    assert device.data.instantaneous.P == 0.0
    print("  => Success")

def test_fuel_empty_fault():
    """연료 고갈 시 FAULT 상태 전이 검증"""
    print("Running test_fuel_empty_fault...")
    device = get_diesel_device()
    now = datetime.now(timezone.utc)
    device.state = DeviceState.RUNNING
    device.current_fuel_l = 1.0 # 1리터만 남음
    device.last_update_time = now
    device.target_p_kw = 1000.0 # 최대 출력으로 소모 가속
    
    # 연료 소모율: 1000 * 0.25 + 5 = 255 L/h -> 약 14초면 소진됨
    future = now + timedelta(seconds=20)
    event = device.tick(future, future)
    
    assert device.state == DeviceState.FAULT
    assert event.event_type == "FUEL_EMPTY"
    assert device.current_fuel_l == 0.0
    print("  => Success")

if __name__ == "__main__":
    print(f"--- Starting Tests for DieselDevice ---")
    print(f"Current Directory: {os.getcwd()}")
    
    tests = [
        test_initial_state,
        test_start_command_and_transition,
        test_load_control_and_fuel_consumption,
        test_stop_command,
        test_fuel_empty_fault
    ]
    
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f"  [FAILED] Assertion Error in {test.__name__}")
            failed += 1
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__} in {test.__name__}: {e}")
            failed += 1
            
    print(f"---------------------------------------")
    if failed == 0:
        print("All tests passed successfully!")
    else:
        print(f"{failed} test(s) failed.")
    
    sys.exit(0 if failed == 0 else 1)
