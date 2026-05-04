from __future__ import annotations

import argparse
import calendar
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


KST = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GK2A LE2 archive downloads month by month.")
    parser.add_argument("--config", default="ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml")
    parser.add_argument("--start-month", default="2025-01", help="YYYY-MM")
    parser.add_argument("--end-month", default="2025-12", help="YYYY-MM")
    parser.add_argument("--minute-offset", type=int, default=None, help="0 for HH00, 30 for HH30, etc.")
    parser.add_argument("--stop-on-failure", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def month_tokens(start_month: str, end_month: str) -> list[tuple[int, int]]:
    start = datetime.strptime(start_month, "%Y-%m")
    end = datetime.strptime(end_month, "%Y-%m")
    cursor = datetime(start.year, start.month, 1)
    months: list[tuple[int, int]] = []
    while cursor <= end:
        months.append((cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = datetime(cursor.year + 1, 1, 1)
        else:
            cursor = datetime(cursor.year, cursor.month + 1, 1)
    return months


def month_window(year: int, month: int, minute_offset: int) -> tuple[str, str]:
    last_day = calendar.monthrange(year, month)[1]
    start = datetime(year, month, 1, 0, minute_offset, tzinfo=KST)
    end = datetime(year, month, last_day, 23, minute_offset, tzinfo=KST)
    return start.isoformat(), end.isoformat()


def compact_summary(payload: dict | None) -> dict | None:
    if not isinstance(payload, dict):
        return None
    keys = [
        "source",
        "start_time",
        "end_time",
        "frequency_minutes",
        "products",
        "area",
        "records",
        "completed",
        "skipped_exists",
        "failed",
        "manifest_path",
    ]
    return {key: payload.get(key) for key in keys if key in payload}


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    configured_start = datetime.fromisoformat(config["collection"]["start_time"])
    minute_offset = args.minute_offset if args.minute_offset is not None else configured_start.minute

    results = []
    script_path = Path("ems/ai/scripts/collect_gk2a_le2_archive.py")
    for year, month in month_tokens(args.start_month, args.end_month):
        start_time, end_time = month_window(year, month, minute_offset)
        command = [
            sys.executable,
            str(script_path),
            "--config",
            args.config,
            "--start-time",
            start_time,
            "--end-time",
            end_time,
        ]
        if args.dry_run:
            command.append("--dry-run")

        completed = subprocess.run(command, text=True, capture_output=True)
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        month_result = {
            "month": f"{year:04d}-{month:02d}",
            "minute_offset": minute_offset,
            "returncode": completed.returncode,
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-2000:],
        }
        try:
            month_result["summary"] = compact_summary(json.loads(stdout))
        except Exception:
            month_result["summary"] = None
        results.append(month_result)

        print(json.dumps(month_result, indent=2, ensure_ascii=False))
        if completed.returncode != 0 and args.stop_on_failure:
            break

    failed = sum(1 for result in results if result["returncode"] != 0)
    print(
        json.dumps(
            {
                "config": args.config,
                "start_month": args.start_month,
                "end_month": args.end_month,
                "minute_offset": minute_offset,
                "months": len(results),
                "failed_months": failed,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
