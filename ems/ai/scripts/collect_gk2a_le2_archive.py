from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Archive GK2A LE2 NetCDF products from KMA APIHub.")
    parser.add_argument("--config", default="ems/ai/configs/data_sources/gk2a_le2_cloud_archive_hourly_2025.yaml")
    parser.add_argument("--start-time", default=None, help="Override ISO start time, e.g. 2025-01-01T00:00:00+09:00")
    parser.add_argument("--end-time", default=None, help="Override ISO end time, e.g. 2025-01-01T03:00:00+09:00")
    parser.add_argument("--limit", type=int, default=None, help="Maximum successful downloads per product.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_env(config: dict[str, Any]) -> None:
    env_file = config.get("request", {}).get("env_file")
    if env_file and load_dotenv is not None:
        load_dotenv(env_file)
    elif env_file:
        with Path(env_file).open("r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                name, value = stripped.split("=", 1)
                os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def auth_key(config: dict[str, Any]) -> str:
    name = config["request"].get("auth_env", "KMA_AUTH_KEY")
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set.")
    return value


def parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError(f"Time must include timezone offset: {value}")
    return parsed


def iter_times(start: datetime, end: datetime, frequency_minutes: int) -> list[datetime]:
    if end < start:
        raise ValueError("end_time must be greater than or equal to start_time.")
    step = timedelta(minutes=frequency_minutes)
    cursor = start
    timestamps: list[datetime] = []
    while cursor <= end:
        timestamps.append(cursor)
        cursor += step
    return timestamps


def token(timestamp: datetime) -> str:
    return timestamp.strftime("%Y%m%d%H%M")


def output_path(root: Path, product: str, area: str, timestamp: datetime) -> Path:
    stamp = token(timestamp)
    return root / product / area / stamp[:4] / stamp[4:6] / stamp[6:8] / f"gk2a_le2_{product}_{area}_{stamp}.nc"


def download_file(url: str, params: dict[str, Any], path: Path, config: dict[str, Any]) -> dict[str, Any]:
    retries = int(config["request"].get("retries", 3))
    timeout = int(config["request"].get("timeout_seconds", 120))
    temp_path = path.with_suffix(path.suffix + ".part")
    path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, params=params, timeout=timeout, stream=True) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "json" in content_type.lower():
                    body = response.text
                    raise RuntimeError(f"Unexpected JSON response: {body[:300]}")
                bytes_written = 0
                with temp_path.open("wb") as file:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        file.write(chunk)
                        bytes_written += len(chunk)
                temp_path.replace(path)
                return {
                    "status": "COMPLETED",
                    "bytes": bytes_written,
                    "content_type": content_type,
                }
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 10))
    raise RuntimeError("Unreachable retry state.")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env(config)
    key = auth_key(config)

    collection = config["collection"]
    start = parse_time(args.start_time or collection["start_time"])
    end = parse_time(args.end_time or collection["end_time"])
    area = collection.get("area", "KO")
    products = list(collection.get("products", ["CLA", "CLD"]))
    timestamps = iter_times(start, end, int(collection.get("frequency_minutes", 60)))
    root = Path(config["storage"]["raw_root"])
    overwrite = bool(config["storage"].get("overwrite", False))
    base_url = config["request"]["base_url"].rstrip("/")

    manifest: list[dict[str, Any]] = []
    completed_by_product = {product: 0 for product in products}
    for timestamp in timestamps:
        stamp = token(timestamp)
        for product in products:
            path = output_path(root, product, area, timestamp)
            record: dict[str, Any] = {
                "product": product,
                "area": area,
                "date": stamp,
                "path": str(path),
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            if path.exists() and not overwrite:
                record.update({"status": "SKIPPED_EXISTS", "bytes": path.stat().st_size})
                manifest.append(record)
                continue
            if args.limit is not None and completed_by_product[product] >= args.limit:
                record.update({"status": "SKIPPED_LIMIT"})
                manifest.append(record)
                continue

            url = f"{base_url}/{product}/{area}/data"
            params = {"date": stamp, "authKey": key}
            if args.dry_run:
                record.update({"status": "DRY_RUN", "url": url})
                manifest.append(record)
                continue

            try:
                result = download_file(url, params, path, config)
                completed_by_product[product] += 1
                record.update(result)
            except Exception as exc:
                record.update({"status": "FAILED", "error": str(exc)})
            record["saved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            manifest.append(record)
            time.sleep(float(config["request"].get("sleep_seconds", 0.2)))

    output = {
        "source": config.get("source"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "frequency_minutes": int(collection.get("frequency_minutes", 60)),
        "products": products,
        "area": area,
        "records": len(manifest),
        "completed": sum(1 for item in manifest if item["status"] == "COMPLETED"),
        "skipped_exists": sum(1 for item in manifest if item["status"] == "SKIPPED_EXISTS"),
        "failed": sum(1 for item in manifest if item["status"] == "FAILED"),
        "manifest": manifest,
    }
    if bool(config["storage"].get("save_manifest", True)) and not args.dry_run:
        manifest_path = root / "manifests" / f"gk2a_le2_{area}_{start:%Y%m%d%H%M}_{end:%Y%m%d%H%M}.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        output["manifest_path"] = str(manifest_path)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
