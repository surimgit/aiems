from __future__ import annotations

import argparse
import calendar
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml


KST = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run GK2A LE2 archive downloads month by month.")
    parser.add_argument("--config", default="ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml")
    parser.add_argument("--start-month", default=None, help="YYYY-MM. Defaults to config collection start month.")
    parser.add_argument("--end-month", default=None, help="YYYY-MM. Defaults to config collection end month.")
    parser.add_argument("--minute-offset", type=int, default=None, help="0 for HH00, 30 for HH30, etc.")
    parser.add_argument(
        "--month-sleep-seconds",
        type=float,
        default=5.0,
        help="Cooldown between months in single-process mode.",
    )
    parser.add_argument(
        "--failure-sleep-seconds",
        type=float,
        default=60.0,
        help="Cooldown after a failed month before continuing or stopping.",
    )
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


def expected_records_for_month(year: int, month: int, products: list[str]) -> int:
    days_in_month = calendar.monthrange(year, month)[1]
    hourly_slots = days_in_month * 24
    return hourly_slots * len(products)


def month_existing_records(root: Path, products: list[str], area: str, year: int, month: int) -> int:
    total = 0
    year_token = f"{year:04d}"
    month_token = f"{month:02d}"
    for product in products:
        month_root = root / product / area / year_token / month_token
        if not month_root.exists():
            continue
        total += sum(1 for _ in month_root.rglob("*.nc"))
    return total


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


def default_month_range(config: dict) -> tuple[str, str]:
    collection = config["collection"]
    start = datetime.fromisoformat(collection["start_time"])
    end = datetime.fromisoformat(collection["end_time"])
    return start.strftime("%Y-%m"), end.strftime("%Y-%m")


def detect_resume_month(config: dict, months: list[tuple[int, int]]) -> str | None:
    collection = config["collection"]
    products = list(collection.get("products", ["CLA", "CLD"]))
    area = collection.get("area", "KO")
    root = Path(config["storage"]["raw_root"])

    for year, month in months:
        expected = expected_records_for_month(year, month, products)
        existing = month_existing_records(root, products, area, year, month)
        if existing < expected:
            return f"{year:04d}-{month:02d}"
    return None


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    configured_start = datetime.fromisoformat(config["collection"]["start_time"])
    minute_offset = args.minute_offset if args.minute_offset is not None else configured_start.minute
    default_start_month, default_end_month = default_month_range(config)
    requested_end_month = args.end_month or default_end_month
    baseline_months = month_tokens(default_start_month, requested_end_month)
    auto_resume_month = detect_resume_month(config, baseline_months)
    start_month = args.start_month or auto_resume_month or default_start_month
    end_month = requested_end_month

    results = []
    script_path = Path("ems/ai/scripts/collect_gk2a_le2_archive.py")
    months = month_tokens(start_month, end_month)
    total_months = len(months)
    collection = config["collection"]
    products = list(collection.get("products", ["CLA", "CLD"]))
    area = collection.get("area", "KO")
    root = Path(config["storage"]["raw_root"])
    for index, (year, month) in enumerate(months, start=1):
        expected = expected_records_for_month(year, month, products)
        existing = month_existing_records(root, products, area, year, month)
        if existing >= expected and not args.dry_run:
            month_result = {
                "month": f"{year:04d}-{month:02d}",
                "minute_offset": minute_offset,
                "returncode": 0,
                "stdout_tail": "",
                "stderr_tail": "",
                "summary": {
                    "source": config.get("source"),
                    "products": products,
                    "area": area,
                    "records": expected,
                    "completed": 0,
                    "skipped_exists": existing,
                    "failed": 0,
                    "status": "SKIPPED_MONTH_COMPLETE",
                    "expected_records": expected,
                    "existing_records": existing,
                },
            }
            results.append(month_result)
            print(json.dumps(month_result, indent=2, ensure_ascii=False))
            if index < total_months and args.month_sleep_seconds > 0:
                time.sleep(args.month_sleep_seconds)
            continue

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
        if completed.returncode != 0:
            time.sleep(max(args.failure_sleep_seconds, 0.0))
            if args.stop_on_failure:
                break
        elif index < total_months and args.month_sleep_seconds > 0:
            time.sleep(args.month_sleep_seconds)

    failed = sum(1 for result in results if result["returncode"] != 0)
    print(
        json.dumps(
            {
                "config": args.config,
                "start_month": start_month,
                "end_month": end_month,
                "minute_offset": minute_offset,
                "months": len(results),
                "failed_months": failed,
                "mode": "single_process_sequential",
                "auto_resume_month": auto_resume_month,
                "month_sleep_seconds": args.month_sleep_seconds,
                "failure_sleep_seconds": args.failure_sleep_seconds,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
