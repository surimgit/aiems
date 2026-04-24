from __future__ import annotations

import argparse
import calendar
import json
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from requests import HTTPError


@dataclass
class MonthWindow:
    year: int
    month: int

    @property
    def token(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def start_date(self) -> str:
        return f"{self.year:04d}{self.month:02d}01"

    @property
    def end_date(self) -> str:
        last_day = calendar.monthrange(self.year, self.month)[1]
        return f"{self.year:04d}{self.month:02d}{last_day:02d}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect West Power renewable generation data by month and normalize it to hourly CSV."
    )
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/west_power_api_example.yaml",
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
    root = Path(config["storage"]["raw_root"]) / region_slug
    return {
        "root": root,
        "metadata": root / "metadata",
        "monthly_raw": root / "monthly_raw",
        "daily_csv": root / "daily_csv",
        "hourly_csv": root / "hourly_csv",
    }


def ensure_layout(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def xml_local_name(element: ET.Element) -> str:
    return element.tag.split("}", 1)[-1]


def find_first(element: ET.Element, name: str) -> ET.Element | None:
    for node in element.iter():
        if xml_local_name(node) == name:
            return node
    return None


def find_text(element: ET.Element, name: str, default: str = "") -> str:
    node = find_first(element, name)
    if node is None or node.text is None:
        return default
    return node.text.strip()


def request_month_page(config: dict, window: MonthWindow, page_no: int) -> str:
    request_config = config["request"]
    auth_key = os.environ.get(request_config["auth_env"])
    if not auth_key:
        raise RuntimeError(f"Environment variable {request_config['auth_env']} is not set.")

    params = {
        "serviceKey": auth_key,
        "pageNo": page_no,
        "numOfRows": request_config.get("num_of_rows", 500),
        "startDate": window.start_date,
        "endDate": window.end_date,
    }

    response_type = request_config.get("response_type")
    if response_type:
        params["type"] = response_type

    retries = request_config.get("retries", 3)
    timeout = request_config.get("timeout_seconds", 30)
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(request_config["base_url"], params=params, timeout=timeout)
            response.raise_for_status()
            if not response.text.strip():
                raise RuntimeError("Empty response body.")
            return response.text
        except HTTPError as error:
            if error.response is not None and error.response.status_code == 429:
                if attempt == retries:
                    raise
                time.sleep(max(10, attempt * 10))
                continue
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
    raise RuntimeError("Unreachable retry state.")


def parse_xml_payload(raw_xml: str) -> tuple[pd.DataFrame, dict]:
    root = ET.fromstring(raw_xml)

    result_code = find_text(root, "resultCode")
    result_msg = find_text(root, "resultMsg")
    if result_code and result_code != "00":
        raise RuntimeError(f"West Power API error: resultCode={result_code}, resultMsg={result_msg}")

    total_count_text = find_text(root, "totalCount", "0")
    page_no_text = find_text(root, "pageNo", "1")
    num_of_rows_text = find_text(root, "numOfRows", "0")

    records: list[dict[str, object]] = []
    for item in root.iter():
        if xml_local_name(item) != "item":
            continue
        if not any(xml_local_name(child) == "date" for child in item):
            continue

        row = {
            "date": find_text(item, "date"),
            "generator_name": find_text(item, "genNm"),
            "installed_capacity_mw": find_text(item, "qcap"),
        }
        for hour in range(1, 25):
            row[f"q{hour:02d}"] = find_text(item, f"q{hour:02d}")
        records.append(row)

    frame = pd.DataFrame(records)
    if not frame.empty:
        numeric_columns = ["installed_capacity_mw"] + [f"q{hour:02d}" for hour in range(1, 25)]
        for column in numeric_columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    payload_meta = {
        "result_code": result_code,
        "result_msg": result_msg,
        "page_no": int(page_no_text or "1"),
        "num_of_rows": int(num_of_rows_text or "0"),
        "total_count": int(total_count_text or "0"),
    }
    return frame, payload_meta


def collect_month(config: dict, window: MonthWindow) -> tuple[str, pd.DataFrame, dict]:
    pages: list[str] = []
    frames: list[pd.DataFrame] = []
    page_no = 1
    total_count = None
    num_of_rows = None

    while True:
        raw_xml = request_month_page(config, window, page_no)
        frame, payload_meta = parse_xml_payload(raw_xml)

        pages.append(raw_xml)
        if not frame.empty:
            frames.append(frame)

        if total_count is None:
            total_count = payload_meta["total_count"]
            num_of_rows = payload_meta["num_of_rows"] or config["request"].get("num_of_rows", 500)

        if total_count == 0 or page_no * num_of_rows >= total_count:
            break

        page_no += 1
        time.sleep(config["request"].get("sleep_seconds", 0.2))

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    merged_xml = "\n".join(pages)
    meta = {
        "pages": page_no,
        "total_count": total_count or 0,
        "rows": int(len(combined)),
    }
    return merged_xml, combined, meta


def hour_ending_to_timestamp(date_series: pd.Series, hour_series: pd.Series) -> pd.Series:
    normalized_dates = date_series.astype(str).str.replace("-", "", regex=False)
    base_dates = pd.to_datetime(normalized_dates, format="%Y%m%d")
    return base_dates + pd.to_timedelta(hour_series.astype(int), unit="h")


def normalize_hourly(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "date",
                "hour_ending",
                "generator_name",
                "installed_capacity_mw",
                "installed_capacity_kw",
                "generation_wh",
                "generation_kwh",
                "generation_kw",
                "capacity_factor",
                "source",
            ]
        )

    hour_columns = [f"q{hour:02d}" for hour in range(1, 25)]
    melted = frame.melt(
        id_vars=["date", "generator_name", "installed_capacity_mw"],
        value_vars=hour_columns,
        var_name="hour_code",
        value_name="generation_wh",
    )

    melted["hour_ending"] = melted["hour_code"].str.replace("q", "", regex=False).astype(int)
    melted["timestamp"] = hour_ending_to_timestamp(melted["date"], melted["hour_ending"])
    melted["installed_capacity_kw"] = melted["installed_capacity_mw"] * 1000.0
    melted["generation_kwh"] = melted["generation_wh"] / 1000.0
    melted["generation_kw"] = melted["generation_kwh"]
    melted["capacity_factor"] = (
        melted["generation_kw"] / melted["installed_capacity_kw"]
    ).where(melted["installed_capacity_kw"] > 0)
    melted["source"] = "west_power_api"

    normalized = melted[
        [
            "timestamp",
            "date",
            "hour_ending",
            "generator_name",
            "installed_capacity_mw",
            "installed_capacity_kw",
            "generation_wh",
            "generation_kwh",
            "generation_kw",
            "capacity_factor",
            "source",
        ]
    ].sort_values(["timestamp", "generator_name"]).reset_index(drop=True)
    return normalized


def write_month(
    paths: dict[str, Path],
    window: MonthWindow,
    raw_xml: str,
    daily_frame: pd.DataFrame,
    hourly_frame: pd.DataFrame,
    config: dict,
) -> None:
    yearly_raw = paths["monthly_raw"] / str(window.year)
    yearly_daily = paths["daily_csv"] / str(window.year)
    yearly_hourly = paths["hourly_csv"] / str(window.year)
    yearly_raw.mkdir(parents=True, exist_ok=True)
    yearly_daily.mkdir(parents=True, exist_ok=True)
    yearly_hourly.mkdir(parents=True, exist_ok=True)

    if config["storage"].get("save_raw_response", True):
        (yearly_raw / f"{window.token}.xml").write_text(raw_xml, encoding="utf-8")

    if config["storage"].get("save_daily_csv", True):
        daily_frame.to_csv(yearly_daily / f"{window.token}.csv", index=False, encoding="utf-8-sig")

    if config["storage"].get("save_hourly_csv", True):
        hourly_frame.to_csv(yearly_hourly / f"{window.token}.csv", index=False, encoding="utf-8-sig")


def month_already_collected(paths: dict[str, Path], window: MonthWindow) -> bool:
    hourly_path = paths["hourly_csv"] / str(window.year) / f"{window.token}.csv"
    daily_path = paths["daily_csv"] / str(window.year) / f"{window.token}.csv"
    raw_path = paths["monthly_raw"] / str(window.year) / f"{window.token}.xml"
    return hourly_path.exists() and daily_path.exists() and raw_path.exists()


def append_manifest(paths: dict[str, Path], payload: dict) -> None:
    manifest_path = paths["metadata"] / "monthly_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_collection_config(paths: dict[str, Path], config: dict) -> None:
    config_path = paths["metadata"] / "collection_config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env_file(config)

    paths = build_paths(config)
    ensure_layout(paths)
    write_collection_config(paths, config)

    windows = month_range(config["range"]["start_month"], config["range"]["end_month"])

    for window in windows:
        if month_already_collected(paths, window):
            print(f"Skip already collected month: {window.token}")
            continue

        started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        raw_xml, daily_frame, meta = collect_month(config, window)
        hourly_frame = normalize_hourly(daily_frame)
        write_month(paths, window, raw_xml, daily_frame, hourly_frame, config)

        append_manifest(
            paths,
            {
                "month": window.token,
                "region_slug": config["region_slug"],
                "rows_daily": int(len(daily_frame)),
                "rows_hourly": int(len(hourly_frame)),
                "pages": meta["pages"],
                "total_count": meta["total_count"],
                "started_at": started_at,
                "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
        )

        time.sleep(config["request"].get("sleep_seconds", 0.2))


if __name__ == "__main__":
    main()
