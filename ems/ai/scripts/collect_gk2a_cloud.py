from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


KST = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect GK2A cloud analysis/detection area values.")
    parser.add_argument("--config", default="ems/ai/configs/data_sources/gk2a_cloud_area_example.yaml")
    parser.add_argument("--date-time", default=None, help="KST yyyymmddHHMM. Defaults to config or now-6h.")
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


def default_date_time(config: dict[str, Any], override: str | None) -> str:
    if override:
        return override
    configured = config.get("collection", {}).get("date_time")
    if configured:
        return str(configured)
    timestamp = datetime.now(KST) - timedelta(hours=6)
    timestamp = timestamp.replace(minute=0, second=0, microsecond=0)
    return timestamp.strftime("%Y%m%d%H%M")


def request_json(url: str, params: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    retries = int(config["request"].get("retries", 3))
    timeout = int(config["request"].get("timeout_seconds", 30))
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
    raise RuntimeError("Unreachable retry state.")


def items_from_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    response = payload.get("response", {})
    header = response.get("header", {})
    if header.get("resultCode") not in (None, "00"):
        raise RuntimeError(f"GK2A API error {header.get('resultCode')}: {header.get('resultMsg')}")
    items = response.get("body", {}).get("items", {}).get("item", [])
    if isinstance(items, dict):
        return [items]
    return list(items)


def output_root(config: dict[str, Any], date_time: str) -> Path:
    root = Path(config["storage"]["raw_root"]) / date_time
    root.mkdir(parents=True, exist_ok=True)
    return root


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env(config)
    key = auth_key(config)
    date_time = default_date_time(config, args.date_time)
    root = output_root(config, date_time)

    records: list[dict[str, Any]] = []
    manifest: list[dict[str, Any]] = []
    collection = config["collection"]
    for site in config.get("sites", []):
        for endpoint_name, url in config["request"]["base_urls"].items():
            result_type = collection["result_types"][endpoint_name]
            params = {
                "pageNo": 1,
                "numOfRows": collection.get("num_of_rows", 10),
                "dataType": collection.get("data_type", "JSON"),
                "dateTime": date_time,
                "resultType": result_type,
                "dongCode": site["dong_code"],
                "authKey": key,
            }
            started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                payload = request_json(url, params, config)
                if config["storage"].get("save_raw_response", True):
                    raw_path = root / endpoint_name / f"{site['site_id']}.json"
                    raw_path.parent.mkdir(parents=True, exist_ok=True)
                    raw_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
                items = items_from_response(payload)
                for item in items:
                    records.append(
                        {
                            "site_id": site["site_id"],
                            "region": site.get("region"),
                            "dong_code": site["dong_code"],
                            "endpoint": endpoint_name,
                            "result_type": result_type,
                            "date_time": item.get("dateTime", date_time),
                            "longitude": pd.to_numeric(item.get("lon"), errors="coerce"),
                            "latitude": pd.to_numeric(item.get("lat"), errors="coerce"),
                            "unit": item.get("unit"),
                            "value": pd.to_numeric(item.get("value"), errors="coerce"),
                        }
                    )
                manifest.append(
                    {
                        "site_id": site["site_id"],
                        "endpoint": endpoint_name,
                        "status": "COMPLETED",
                        "rows": len(items),
                        "started_at": started_at,
                        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                )
            except Exception as exc:
                manifest.append(
                    {
                        "site_id": site["site_id"],
                        "endpoint": endpoint_name,
                        "status": "FAILED",
                        "error": str(exc),
                        "started_at": started_at,
                        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                )
            time.sleep(float(config["request"].get("sleep_seconds", 0.5)))

    frame = pd.DataFrame(records)
    csv_path = root / "gk2a_cloud_area_values.csv"
    if config["storage"].get("save_parsed_csv", True):
        frame.to_csv(csv_path, index=False, encoding="utf-8-sig")

    output = {
        "source": config.get("source"),
        "date_time": date_time,
        "rows": int(len(frame)),
        "csv_path": str(csv_path),
        "manifest": manifest,
    }
    if config["storage"].get("save_manifest", True):
        (root / "collection_manifest.json").write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
