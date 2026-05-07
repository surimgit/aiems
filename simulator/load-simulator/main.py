from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path
from typing import Sequence

from runtime_config import load_config
from simulator_app import LoadSimulatorApp


# CLI 인자를 정의하고 기본 실행 옵션을 구성한다.
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load simulator runtime entrypoint")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config" / "devices.yaml"),
        help="Path to load device config file",
    )
    parser.add_argument(
        "--scenario",
        default=str(Path(__file__).resolve().parent / "config" / "scenario.yaml"),
        help="Path to scenario profile config file",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        help="Run a fixed number of publish cycles and exit",
    )
    return parser


# 설정을 읽고 시뮬레이터 앱을 비동기로 실행한다.
async def async_main(config_path: Path, scenario_path: Path, *, cycles: int | None = None) -> None:
    config = load_config(config_path, scenario_path)
    app = LoadSimulatorApp(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: app.request_shutdown())
        except NotImplementedError:
            pass

    await app.run(max_cycles=cycles)


# 엔트리포인트에서 예외를 처리하며 실행을 시작한다.
def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()
    scenario_path = Path(args.scenario).resolve()

    try:
        asyncio.run(async_main(config_path, scenario_path, cycles=args.cycles))
    except FileNotFoundError as exc:
        print(f"[LOAD] {exc}")
    except ValueError as exc:
        print(f"[LOAD] Invalid config: {exc}")
    except KeyboardInterrupt:
        print("[LOAD] Interrupted by user")


if __name__ == "__main__":
    main()
