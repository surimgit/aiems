from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


GRID_WIDTH = 149
GRID_HEIGHT = 253


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect KMA village forecast grid API raw responses.")
    parser.add_argument("--config", default="ems/ai/configs/data_sources/kma_vilage_forecast_example.yaml")
    parser.add_argument("--tmfc-ultra", default=None, help="KST yyyymmddHHMM for ultra-short APIs.")
    parser.add_argument("--tmef-ultra", default=None, help="KST yyyymmddHH target time for ultra-short forecast.")
    parser.add_argument("--tmfc-short", default=None, help="KST yyyymmddHH for short forecast API.")
    parser.add_argument("--tmef-short", default=None, help="KST yyyymmddHH target time for short forecast.")
    parser.add_argument("--skip-forecast", action="store_true", help="Only resolve site lon/lat to grid x/y.")
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


def request_text(url: str, params: dict[str, Any], config: dict[str, Any]) -> str:
    retries = int(config["request"].get("retries", 3))
    timeout = int(config["request"].get("timeout_seconds", 30))
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
    raise RuntimeError("Unreachable retry state.")


def parse_xy_response(text: str) -> dict[str, Any]:
    data_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not data_lines:
        raise ValueError("No lon/lat/x/y data line found in KMA grid response.")
    parts = [part.strip() for part in data_lines[0].split(",")]
    if len(parts) != 4:
        parts = data_lines[0].split()
    if len(parts) < 4:
        raise ValueError(f"Unexpected KMA grid response line: {data_lines[0]}")
    return {
        "longitude": float(parts[0]),
        "latitude": float(parts[1]),
        "x": int(float(parts[2])),
        "y": int(float(parts[3])),
    }


def output_root(config: dict[str, Any]) -> Path:
    root = Path(config["storage"]["raw_root"])
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_text(path: Path, text: str, enabled: bool) -> None:
    if not enabled:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_grid_values(text: str) -> list[float]:
    values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", text)]
    expected = GRID_WIDTH * GRID_HEIGHT
    if len(values) != expected:
        raise ValueError(f"Expected {expected} grid values, found {len(values)}.")
    return values


def grid_value_at(values: list[float], x: int, y: int) -> float:
    if not (1 <= x <= GRID_WIDTH and 1 <= y <= GRID_HEIGHT):
        raise ValueError(f"Grid coordinate out of range: x={x}, y={y}")
    return values[(y - 1) * GRID_WIDTH + (x - 1)]


def collect_grid_points(config: dict[str, Any], key: str, root: Path) -> list[dict[str, Any]]:
    endpoint = config["request"]["endpoints"]["xy_lonlat"]
    records: list[dict[str, Any]] = []
    for site in config.get("sites", []):
        params = {
            "lon": site["longitude"],
            "lat": site["latitude"],
            "help": 0,
            "authKey": key,
        }
        text = request_text(endpoint, params, config)
        parsed = parse_xy_response(text)
        record = {**site, **parsed}
        records.append(record)
        write_text(
            root / "grid_reference" / f"{site['site_id']}_xy_lonlat.txt",
            text,
            bool(config["storage"].get("save_raw_response", True)),
        )
        time.sleep(float(config["request"].get("sleep_seconds", 0.5)))

    frame = pd.DataFrame(records)
    frame.to_csv(root / "grid_reference" / "site_grid_points.csv", index=False, encoding="utf-8-sig")
    return records


def collect_forecast(args: argparse.Namespace, config: dict[str, Any], key: str, root: Path) -> list[dict[str, Any]]:
    collection = config["collection"]
    endpoints = config["request"]["endpoints"]
    variables = collection["variables"]
    tmfc_ultra = args.tmfc_ultra or collection.get("tmfc_ultra")
    tmef_ultra = args.tmef_ultra or collection.get("tmef_ultra")
    tmfc_short = args.tmfc_short or collection.get("tmfc_short")
    tmef_short = args.tmef_short or collection.get("tmef_short")

    jobs: list[dict[str, Any]] = [
        {
            "name": "ultra_srt_ncst",
            "url": endpoints["ultra_srt_ncst"],
            "tmfc": tmfc_ultra,
            "tmef": None,
        },
        {
            "name": "ultra_srt_fcst",
            "url": endpoints["ultra_srt_fcst"],
            "tmfc": tmfc_ultra,
            "tmef": tmef_ultra,
        },
        {
            "name": "vilage_fcst",
            "url": endpoints["vilage_fcst"],
            "tmfc": tmfc_short,
            "tmef": tmef_short,
        },
    ]

    manifest: list[dict[str, Any]] = []
    for job in jobs:
        if not job["tmfc"]:
            manifest.append({"endpoint": job["name"], "status": "SKIPPED", "reason": "tmfc missing"})
            continue
        for variable in variables.get(job["name"], []):
            params = {"tmfc": job["tmfc"], "vars": variable, "authKey": key}
            if job["tmef"]:
                params["tmef"] = job["tmef"]

            started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                text = request_text(job["url"], params, config)
                relative = Path(job["name"]) / str(job["tmfc"]) / f"{variable}.txt"
                write_text(root / relative, text, bool(config["storage"].get("save_raw_response", True)))
                status = {
                    "endpoint": job["name"],
                    "variable": variable,
                    "tmfc": job["tmfc"],
                    "tmef": job["tmef"],
                    "status": "COMPLETED",
                    "bytes": len(text.encode("utf-8")),
                    "lines": len(text.splitlines()),
                    "path": str(root / relative),
                    "started_at": started_at,
                    "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            except Exception as exc:
                status = {
                    "endpoint": job["name"],
                    "variable": variable,
                    "tmfc": job["tmfc"],
                    "tmef": job["tmef"],
                    "status": "FAILED",
                    "error": str(exc),
                    "started_at": started_at,
                    "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            manifest.append(status)
            time.sleep(float(config["request"].get("sleep_seconds", 0.5)))
    return manifest


def extract_site_forecast_values(
    grid_points: list[dict[str, Any]],
    forecast_manifest: list[dict[str, Any]],
    root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    if not forecast_manifest:
        return {"status": "SKIPPED", "reason": "forecast missing", "rows": 0}

    records: list[dict[str, Any]] = []
    for item in forecast_manifest:
        if item.get("status") != "COMPLETED" or not item.get("path"):
            continue
        values = parse_grid_values(Path(item["path"]).read_text(encoding="utf-8"))
        for site in grid_points:
            value = grid_value_at(values, int(site["x"]), int(site["y"]))
            records.append(
                {
                    "site_id": site["site_id"],
                    "region": site.get("region"),
                    "latitude": site["latitude"],
                    "longitude": site["longitude"],
                    "grid_x": site["x"],
                    "grid_y": site["y"],
                    "endpoint": item["endpoint"],
                    "variable": item["variable"],
                    "tmfc": item["tmfc"],
                    "tmef": item.get("tmef"),
                    "value": value,
                    "is_missing": value <= -90,
                    "source_path": item["path"],
                }
            )

    output_path = root / "site_values" / "latest_site_forecast_values.csv"
    if records and bool(config["storage"].get("save_site_values", True)):
        frame = pd.DataFrame(records)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(output_path, index=False, encoding="utf-8-sig")
    return {
        "status": "COMPLETED" if records else "EMPTY",
        "rows": len(records),
        "site_count": len(grid_points),
        "path": str(output_path) if records and bool(config["storage"].get("save_site_values", True)) else None,
    }


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env(config)
    key = auth_key(config)
    root = output_root(config)

    grid_points = collect_grid_points(config, key, root)
    forecast_manifest = [] if args.skip_forecast else collect_forecast(args, config, key, root)
    site_values = extract_site_forecast_values(grid_points, forecast_manifest, root, config)
    manifest = {
        "source": config.get("source"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "grid_points": grid_points,
        "forecast": forecast_manifest,
        "site_values": site_values,
    }
    if config["storage"].get("save_manifest", True):
        (root / "collection_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
