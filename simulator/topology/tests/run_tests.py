"""
topology wire_fault 통합 테스트 러너

실행:
  docker run --rm --network simulator_ems_default \\
    --add-host host.docker.internal:host-gateway \\
    -e MQTT_HOST=host.docker.internal \\
    -e SM_URL=http://simulator-manager:8080 \\
    -e TOPO_URL=http://topology:8081 \\
    -v $(pwd)/tests:/tests -w /tests \\
    python:3.10-slim sh -c "pip install paho-mqtt requests -q && python run_tests.py"

선행 조건:
  1. EMS control 일시 정지 권장: docker stop control
     (운영 rule이 새 test edge에 명령 race 보내는 것 방지)
  2. solar 관련 테스트(solar/shared/toggle)는 시뮬레이터 시간이 야간이면 P=0
     이 됨. 낮 시간대(현지 06~18시)에 실행 권장.
  3. 테스트 종료 후: docker start control

특정 시나리오만 실행:
  python run_tests.py solar ess diesel load
"""

from __future__ import annotations

import sys
import time

import test_01_solar_fault
import test_02_ess_soc_freeze
import test_03_diesel_fault
import test_04_load_fault
import test_05_shared_line_fault
import test_06_ess_discharge_fault
import test_07_rapid_toggle

ALL_SUITES = [
    ("Solar wire_fault (LINE FAULT / SWITCH / ISOLATE)", test_01_solar_fault),
    ("ESS SOC 고정 (wire_fault 중 SOC freeze)",          test_02_ess_soc_freeze),
    ("Diesel wire_fault (RUNNING 중 LINE FAULT)",        test_03_diesel_fault),
    ("Load wire_fault (LINE FAULT / SWITCH OPEN)",       test_04_load_fault),
    ("공유 선로 장애 (Solar + ESS 동시 wire_fault)",       test_05_shared_line_fault),
    ("ESS 방전 중 wire_fault (discharge 모드 유지)",       test_06_ess_discharge_fault),
    ("선로 장애 빠른 반복 토글 (3사이클 안정성)",            test_07_rapid_toggle),
]

FILTER_MAP = {
    "solar":    0,
    "ess":      1,
    "diesel":   2,
    "load":     3,
    "shared":   4,
    "discharge":5,
    "toggle":   6,
}


def main() -> None:
    args = sys.argv[1:]
    if args:
        indices = {FILTER_MAP[a.lower()] for a in args if a.lower() in FILTER_MAP}
        suites = [s for i, s in enumerate(ALL_SUITES) if i in indices]
    else:
        suites = ALL_SUITES

    all_results: list[tuple[str, bool]] = []
    start = time.time()

    for suite_name, module in suites:
        print(f"\n{'='*60}")
        print(f"  {suite_name}")
        print(f"{'='*60}")
        results = module.run()
        all_results.extend(results)

    elapsed = time.time() - start
    passed = sum(1 for _, ok in all_results if ok)
    failed = len(all_results) - passed

    print(f"\n{'='*60}")
    print(f"  결과: {passed} PASS / {failed} FAIL   ({elapsed:.1f}s)")
    print(f"{'='*60}")

    if failed:
        print("\n실패한 항목:")
        for name, ok in all_results:
            if not ok:
                print(f"  ✗ {name}")
        sys.exit(1)
    else:
        print("  모든 테스트 통과")


if __name__ == "__main__":
    main()
