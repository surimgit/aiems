from __future__ import annotations

import argparse
import json
import os
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check KMA station metadata by station id.")
    parser.add_argument(
        "--config",
        default="C:/Users/SSAFY/PycharmProjects/S14P31S305/ems/ai/configs/data_sources/kma_asos_example.yaml",
        help="Path to collector config.",
    )
    parser.add_argument("--station-id", type=int, required=True, help="Station id to lookup.")
    parser.add_argument("--year", type=int, default=2016, help="Reference year for station list API.")
    parser.add_argument("--month", default="09", help="Reference month for station list API.")
    return parser.parse_args()


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def parse_station_payload(payload: dict) -> pd.DataFrame:
    if "response" in payload:
        response = payload["response"]
        body = response.get("body", {}) if isinstance(response, dict) else {}
        items = body.get("items", {}) if isinstance(body, dict) else {}
        item = items.get("item") if isinstance(items, dict) else None

        if isinstance(item, list) and item:
            item = item[0]

        if isinstance(item, dict) and "stn_sfc" in item:
            payload = {"stn_sfc": item["stn_sfc"]}

    if "stn_sfc" not in payload:
        raise ValueError(f"Unexpected payload keys: {list(payload.keys())}")

    raw = payload["stn_sfc"]

    if isinstance(raw, dict) and "info" in raw:
        info = raw["info"]
        if isinstance(info, list):
            return pd.DataFrame(info)
        if isinstance(info, dict):
            return pd.DataFrame([info])

    if isinstance(raw, list):
        return pd.DataFrame(raw)

    if isinstance(raw, dict):
        return pd.DataFrame([raw])

    if isinstance(raw, str):
        text = raw.strip()

        if not text:
            raise ValueError("Empty stn_sfc payload.")

        if text.startswith("["):
            return pd.DataFrame(json.loads(text))

        if text.startswith("{"):
            decoded = json.loads(text)
            if isinstance(decoded, list):
                return pd.DataFrame(decoded)
            if isinstance(decoded, dict):
                return pd.DataFrame([decoded])

        frame = pd.read_csv(StringIO(text))
        return frame

    raise ValueError(f"Unsupported stn_sfc payload type: {type(raw)}")


def normalize_station_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in frame.columns:
        lowered = str(column).strip().lower()
        if lowered in {"stn_id", "stnid", "stnid"}:
            rename_map[column] = "stn_id"
        elif lowered in {"stn_ko", "stnko"}:
            rename_map[column] = "stn_ko"
        elif lowered in {"stn_en", "stnen"}:
            rename_map[column] = "stn_en"
        elif lowered == "lat":
            rename_map[column] = "lat"
        elif lowered == "lon":
            rename_map[column] = "lon"
        elif lowered == "ht":
            rename_map[column] = "ht"
        elif lowered == "ht_pa":
            rename_map[column] = "ht_pa"
        elif lowered == "ht_ta":
            rename_map[column] = "ht_ta"
        elif lowered == "ht_wd":
            rename_map[column] = "ht_wd"
        elif lowered == "ht_rn":
            rename_map[column] = "ht_rn"

    return frame.rename(columns=rename_map)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    env_file = config.get("request", {}).get("env_file")
    if env_file:
        load_dotenv(env_file)

    auth_key = os.getenv(config["request"]["auth_env"])
    if not auth_key:
        raise RuntimeError(f"Missing auth key in env: {config['request']['auth_env']}")

    url = "https://apihub.kma.go.kr/api/typ02/openApi/SfcMtlyInfoService/getSfcStnLstTbl"
    params = {
        "pageNo": 1,
        "numOfRows": 300,
        "dataType": "JSON",
        "year": args.year,
        "month": args.month,
        "authKey": auth_key,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    frame = normalize_station_columns(parse_station_payload(payload))

    print(f"request_url={response.url}")
    print(f"columns={list(frame.columns)}")

    if "stn_id" not in frame.columns:
        raise ValueError(f"Could not find stn_id column. Available columns: {list(frame.columns)}")

    matched = frame[frame["stn_id"].astype(str) == str(args.station_id)]
    if matched.empty:
        print(f"No matched station found for station_id={args.station_id}")
        return

    preferred_columns = [
        column
        for column in ["stn_id", "stn_ko", "stn_en", "lat", "lon", "ht", "ht_pa", "ht_ta", "ht_wd", "ht_rn"]
        if column in matched.columns
    ]
    if preferred_columns:
        matched = matched[preferred_columns]

    print(matched.to_string(index=False))


if __name__ == "__main__":
    main()
