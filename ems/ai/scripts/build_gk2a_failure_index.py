from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml


REJECT_HINTS = (
    "401",
    "403",
    "404",
    "429",
    "NO DATA",
    "NODATA",
    "NOT FOUND",
    "SERVICE",
    "LIMIT",
    "DENIED",
    "UNAUTHORIZED",
    "FORBIDDEN",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a retry index for missing or rejected GK2A LE2 archive files."
    )
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml",
        help="GK2A archive YAML config.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path to write JSON index. Defaults under raw_root/manifests.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        help="Path to write CSV retry list. Defaults next to JSON output.",
    )
    parser.add_argument(
        "--raw-root",
        default=None,
        help="Override config storage.raw_root when Google Drive is mounted at a different path.",
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=1024,
        help="Existing .nc files smaller than this are treated as suspicious.",
    )
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Time must include timezone offset: {value}")
    return parsed


def iter_times(start: datetime, end: datetime, frequency_minutes: int) -> list[datetime]:
    step = timedelta(minutes=frequency_minutes)
    cursor = start
    values: list[datetime] = []
    while cursor <= end:
        values.append(cursor)
        cursor += step
    return values


def token(timestamp: datetime) -> str:
    return timestamp.strftime("%Y%m%d%H%M")


def output_path(root: Path, product: str, area: str, timestamp: datetime) -> Path:
    stamp = token(timestamp)
    return root / product / area / stamp[:4] / stamp[4:6] / stamp[6:8] / f"gk2a_le2_{product}_{area}_{stamp}.nc"


def read_manifest_records(root: Path) -> dict[tuple[str, str], list[dict[str, Any]]]:
    records: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for manifest_path in sorted((root / "manifests").glob("gk2a_le2_*.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for record in payload.get("manifest", []):
            product = str(record.get("product", ""))
            date = str(record.get("date", ""))
            if not product or not date:
                continue
            item = dict(record)
            item["manifest_path"] = str(manifest_path)
            records.setdefault((product, date), []).append(item)
    return records


def latest_record(records: dict[tuple[str, str], list[dict[str, Any]]], product: str, stamp: str) -> dict[str, Any] | None:
    values = records.get((product, stamp), [])
    if not values:
        return None
    return values[-1]


def classify_manifest_failure(record: dict[str, Any] | None) -> tuple[str | None, str | None]:
    if record is None:
        return None, None
    status = str(record.get("status", ""))
    if status not in {"FAILED", "DRY_RUN"}:
        return None, None
    error = str(record.get("error", ""))
    upper = error.upper()
    if any(hint in upper for hint in REJECT_HINTS):
        return "REJECTED_OR_NO_DATA", error
    return "FAILED", error


def build_index(config: dict[str, Any], min_bytes: int) -> dict[str, Any]:
    collection = config["collection"]
    start = parse_time(collection["start_time"])
    end = parse_time(collection["end_time"])
    frequency_minutes = int(collection.get("frequency_minutes", 60))
    area = collection.get("area", "KO")
    products = list(collection.get("products", ["CLA", "CLD"]))
    root = Path(config["storage"]["raw_root"])
    manifest_records = read_manifest_records(root)

    retry_items: list[dict[str, Any]] = []
    completed = 0
    suspicious = 0
    missing = 0
    failed = 0
    rejected = 0

    for timestamp in iter_times(start, end, frequency_minutes):
        stamp = token(timestamp)
        for product in products:
            path = output_path(root, product, area, timestamp)
            record = latest_record(manifest_records, product, stamp)
            manifest_reason, error = classify_manifest_failure(record)
            reason = None
            bytes_on_disk = None

            if path.exists():
                bytes_on_disk = path.stat().st_size
                if bytes_on_disk < min_bytes:
                    reason = "SUSPICIOUS_SMALL_FILE"
                    suspicious += 1
                elif manifest_reason in {"REJECTED_OR_NO_DATA", "FAILED"}:
                    completed += 1
                    continue
                else:
                    completed += 1
                    continue
            elif manifest_reason == "REJECTED_OR_NO_DATA":
                reason = manifest_reason
                rejected += 1
            elif manifest_reason == "FAILED":
                reason = manifest_reason
                failed += 1
            else:
                reason = "MISSING"
                missing += 1

            retry_items.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "date": stamp,
                    "product": product,
                    "area": area,
                    "reason": reason,
                    "path": str(path),
                    "bytes": bytes_on_disk,
                    "last_status": record.get("status") if record else None,
                    "last_error": error,
                    "last_manifest": record.get("manifest_path") if record else None,
                }
            )

    expected = len(iter_times(start, end, frequency_minutes)) * len(products)
    return {
        "source": config.get("source"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "raw_root": str(root),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "frequency_minutes": frequency_minutes,
        "area": area,
        "products": products,
        "expected": expected,
        "completed": completed,
        "retry_count": len(retry_items),
        "missing": missing,
        "failed": failed,
        "rejected_or_no_data": rejected,
        "suspicious_small_file": suspicious,
        "items": retry_items,
    }


def apply_overrides(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.raw_root:
        config = dict(config)
        config["storage"] = dict(config["storage"])
        config["storage"]["raw_root"] = args.raw_root
    return config


def write_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "timestamp",
        "date",
        "product",
        "area",
        "reason",
        "path",
        "bytes",
        "last_status",
        "last_error",
        "last_manifest",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for item in items:
            writer.writerow({column: item.get(column) for column in columns})


def main() -> None:
    args = parse_args()
    config = apply_overrides(load_config(args.config), args)
    root = Path(config["storage"]["raw_root"])
    if root.drive and not Path(root.drive + "\\").exists():
        raise RuntimeError(
            f"Configured raw_root drive is not available: {root.drive}. "
            "Mount Google Drive or pass --raw-root with the actual local path."
        )
    default_json = root / "manifests" / "gk2a_le2_retry_index.json"
    output_json = Path(args.output_json) if args.output_json else default_json
    output_csv = Path(args.output_csv) if args.output_csv else output_json.with_suffix(".csv")

    index = build_index(config, args.min_bytes)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(output_csv, index["items"])

    print(
        json.dumps(
            {
                "output_json": str(output_json),
                "output_csv": str(output_csv),
                "expected": index["expected"],
                "completed": index["completed"],
                "retry_count": index["retry_count"],
                "missing": index["missing"],
                "failed": index["failed"],
                "rejected_or_no_data": index["rejected_or_no_data"],
                "suspicious_small_file": index["suspicious_small_file"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
