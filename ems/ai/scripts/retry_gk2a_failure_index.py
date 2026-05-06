from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retry GK2A LE2 downloads from a retry index.")
    parser.add_argument(
        "--index",
        default="G:/내 드라이브/s305-ai-data/raw/weather/gk2a_le2/manifests/gk2a_le2_retry_index.json",
        help="Retry index JSON produced by build_gk2a_failure_index.py.",
    )
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml",
        help="GK2A archive YAML config.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximum timestamp groups to retry.")
    parser.add_argument(
        "--reasons",
        default="MISSING,FAILED,REJECTED_OR_NO_DATA,SUSPICIOUS_SMALL_FILE",
        help="Comma-separated reasons to retry.",
    )
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Cooldown between timestamp retries.")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_index(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def grouped_timestamps(items: list[dict[str, Any]], reasons: set[str]) -> list[str]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for item in items:
        if item.get("reason") not in reasons:
            continue
        grouped[str(item["timestamp"])].add(str(item["product"]))
    return sorted(grouped)


def run_retry(config: str, timestamp: str, dry_run: bool) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "ems/ai/scripts/collect_gk2a_le2_archive.py",
        "--config",
        config,
        "--start-time",
        timestamp,
        "--end-time",
        timestamp,
    ]
    if dry_run:
        command.append("--dry-run")
    return subprocess.run(command, text=True, capture_output=True)


def compact_stdout(stdout: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(stdout.strip())
    except Exception:
        return None
    keys = ["records", "completed", "skipped_exists", "failed", "manifest_path"]
    return {key: payload.get(key) for key in keys if key in payload}


def main() -> None:
    args = parse_args()
    index = load_index(args.index)
    reasons = {value.strip() for value in args.reasons.split(",") if value.strip()}
    timestamps = grouped_timestamps(index.get("items", []), reasons)
    if args.limit is not None:
        timestamps = timestamps[: args.limit]

    results = []
    for timestamp in timestamps:
        completed = run_retry(args.config, timestamp, args.dry_run)
        result = {
            "timestamp": timestamp,
            "returncode": completed.returncode,
            "summary": compact_stdout(completed.stdout),
            "stdout_tail": completed.stdout.strip()[-1000:],
            "stderr_tail": completed.stderr.strip()[-1000:],
        }
        results.append(result)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if completed.returncode != 0 and args.stop_on_failure:
            break
        if args.sleep_seconds > 0:
            time.sleep(args.sleep_seconds)

    print(
        json.dumps(
            {
                "index": args.index,
                "requested_timestamps": len(timestamps),
                "attempted": len(results),
                "failed_processes": sum(1 for result in results if result["returncode"] != 0),
                "dry_run": args.dry_run,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
