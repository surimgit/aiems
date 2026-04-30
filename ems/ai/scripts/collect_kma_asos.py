from __future__ import annotations

import argparse
import calendar
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

KMA_ASOS_COLUMNS = [
    "TM",
    "STN",
    "WD",
    "WS",
    "GST_WD",
    "GST_WS",
    "GST_TM",
    "PA",
    "PS",
    "PT",
    "PR",
    "TA",
    "TD",
    "HM",
    "PV",
    "RN",
    "RN_DAY",
    "RN_INT",
    "SD_HR3",
    "SD_DAY",
    "SD_TOT",
    "WC",
    "WP",
    "WW",
    "CA_TOT",
    "CA_MID",
    "CH_MIN",
    "CT",
    "CT_TOP",
    "CT_MID",
    "CT_LOW",
    "VS",
    "SS",
    "SI",
    "ST_GD",
    "TS",
    "TE_005",
    "TE_01",
    "TE_02",
    "TE_03",
    "ST_SEA",
    "WH",
    "BF",
    "IR",
    "IX",
    "RN_JUN",
]


@dataclass
class MonthWindow:
    year: int
    month: int

    @property
    def token(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def start_tm(self) -> str:
        return f"{self.year:04d}{self.month:02d}010000"

    @property
    def end_tm(self) -> str:
        last_day = calendar.monthrange(self.year, self.month)[1]
        return f"{self.year:04d}{self.month:02d}{last_day:02d}2359"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect KMA ASOS hourly data by month.")
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/kma_asos_example.yaml",
        help="Path to YAML config.",
    )
    return parser.parse_args()


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_env_file(config: dict) -> None:
    env_file = config.get("request", {}).get("env_file")
    if env_file:
        load_dotenv(env_file)


def month_range(start_month: str, end_month: str) -> list[MonthWindow]:
    start = datetime.strptime(start_month, "%Y-%m")
    end = datetime.strptime(end_month, "%Y-%m")

    cursor = datetime(start.year, start.month, 1)
    windows: list[MonthWindow] = []
    while cursor <= end:
        windows.append(MonthWindow(cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = datetime(cursor.year + 1, 1, 1)
        else:
            cursor = datetime(cursor.year, cursor.month + 1, 1)
    return windows


def build_paths(config: dict) -> dict[str, Path]:
    region_slug = config["region_slug"]
    station_id = config["station_id"]
    root = Path(config["storage"]["raw_root"]) / region_slug / f"station_{station_id}"
    return {
        "root": root,
        "metadata": root / "metadata",
        "hourly_raw": root / "hourly_raw",
        "hourly_csv": root / "hourly_csv",
    }


def ensure_layout(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def request_month(config: dict, window: MonthWindow) -> str:
    request_config = config["request"]
    auth_key = os.environ.get(request_config["auth_env"])
    if not auth_key:
        raise RuntimeError(f"Environment variable {request_config['auth_env']} is not set.")

    params = {
        "tm1": window.start_tm,
        "tm2": window.end_tm,
        "stn": config["station_id"],
        "help": request_config.get("help", 0),
        "authKey": auth_key,
    }

    retries = request_config.get("retries", 3)
    timeout = request_config.get("timeout_seconds", 30)
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(request_config["base_url"], params=params, timeout=timeout)
            response.raise_for_status()
            if not response.text.strip():
                raise RuntimeError("Empty response body.")
            return response.text
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
    raise RuntimeError("Unreachable retry state.")


def parse_asos_text(raw_text: str) -> pd.DataFrame:
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)

    if not lines:
        raise ValueError("No data lines found in KMA response.")

    frame = pd.read_csv(
        StringIO("\n".join(lines)),
        sep=r"\s+",
        engine="python",
        header=None,
        names=KMA_ASOS_COLUMNS,
    )
    if len(frame.columns) != len(KMA_ASOS_COLUMNS):
        raise ValueError(
            f"Unexpected parsed column count: {len(frame.columns)} (expected {len(KMA_ASOS_COLUMNS)})"
        )
    return frame


def write_month(paths: dict[str, Path], window: MonthWindow, raw_text: str, frame: pd.DataFrame, config: dict) -> None:
    yearly_raw = paths["hourly_raw"] / str(window.year)
    yearly_csv = paths["hourly_csv"] / str(window.year)
    yearly_raw.mkdir(parents=True, exist_ok=True)
    yearly_csv.mkdir(parents=True, exist_ok=True)

    if config["storage"].get("save_raw_response", True):
        (yearly_raw / f"{window.token}.txt").write_text(raw_text, encoding="utf-8")

    if config["storage"].get("save_parsed_csv", True):
        frame.to_csv(yearly_csv / f"{window.token}.csv", index=False, encoding="utf-8")


def append_manifest(paths: dict[str, Path], payload: dict) -> None:
    manifest_path = paths["metadata"] / "monthly_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=True) + "\n")


def write_collection_config(paths: dict[str, Path], config: dict) -> None:
    config_path = paths["metadata"] / "collection_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env_file(config)

    paths = build_paths(config)
    ensure_layout(paths)
    write_collection_config(paths, config)

    windows = month_range(config["range"]["start_month"], config["range"]["end_month"])

    for window in windows:
        started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        raw_text = request_month(config, window)
        frame = parse_asos_text(raw_text)
        write_month(paths, window, raw_text, frame, config)

        append_manifest(
            paths,
            {
                "month": window.token,
                "station_id": config["station_id"],
                "region_slug": config["region_slug"],
                "rows": int(len(frame)),
                "columns": list(frame.columns),
                "started_at": started_at,
                "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
        )

        time.sleep(config["request"].get("sleep_seconds", 0.5))


if __name__ == "__main__":
    main()
