from __future__ import annotations

import argparse
import asyncio
import signal
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from runtime_config import load_config
from simulator_app import EssSimulatorApp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ESS simulator runtime entrypoint")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config" / "devices.yaml"),
        help="Path to ESS device config file",
    )
    return parser


async def async_main(config_path: Path) -> None:
    config = load_config(config_path)
    app = EssSimulatorApp(config)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            # noinspection PyTypeChecker
            loop.add_signal_handler(sig, lambda : app.request_shutdown())
        except NotImplementedError:
            pass

    await app.run()


def main(argv: Sequence[str] | None = None) -> None:
    """Parse CLI args and run the simulator entrypoint."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config).resolve()

    try:
        asyncio.run(async_main(config_path))
    except ValidationError as exc:
        print(f"[ESS] Invalid config:\n{exc}")
    except FileNotFoundError as exc:
        print(f"[ESS] {exc}")
    except KeyboardInterrupt:
        print("[ESS] Interrupted by user")


if __name__ == "__main__":
    main()
