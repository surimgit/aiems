from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
import yaml
from dotenv import load_dotenv
from pandas.errors import EmptyDataError
from requests import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect KPX hourly solar generation by region.")
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/kpx_solar_api_example.yaml",
        help="Path to YAML config.",
    )
    parser.add_argument("--start-date", help="Override range.start_date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Override range.end_date, YYYY-MM-DD.")
    parser.add_argument("--max-requests", type=int, help="Override range.max_requests.")
    return parser.parse_args()


def resolve_existing_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.exists():
        return candidate

    repo_candidate = REPO_ROOT / candidate
    if repo_candidate.exists():
        return repo_candidate

    return candidate


def load_config(path: str | Path) -> dict:
    config_path = resolve_existing_path(path)
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def apply_args(config: dict, args: argparse.Namespace) -> dict:
    if args.start_date:
        config["range"]["start_date"] = args.start_date
    if args.end_date:
        config["range"]["end_date"] = args.end_date
    if args.max_requests is not None:
        config["range"]["max_requests"] = args.max_requests
    return config


def load_env_file(config: dict) -> None:
    env_file = config.get("request", {}).get("env_file")
    if env_file:
        load_dotenv(resolve_existing_path(env_file))


def resolve_auth_key(config: dict) -> tuple[str, str, bool]:
    request_config = config["request"]
    candidates = []
    if request_config.get("auth_env"):
        candidates.append(request_config["auth_env"])
    candidates.extend(request_config.get("auth_env_candidates") or [])

    for env_name in candidates:
        auth_key = os.environ.get(env_name)
        if auth_key:
            is_encoded_key = env_name.upper().endswith("ENCODING")
            return env_name, auth_key, is_encoded_key
    raise RuntimeError(f"No auth key found. Checked: {', '.join(candidates)}")


def date_range(start_date: str, end_date: str) -> list[date]:
    start_date = str(start_date)
    end_date = str(end_date)
    start = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def build_paths(config: dict) -> dict[str, Path]:
    root = Path(config["storage"]["raw_root"]) / config["region_slug"] / "api"
    return {
        "root": root,
        "metadata": root / "metadata",
        "daily_raw": root / "daily_raw",
        "daily_csv": root / "daily_csv",
        "hourly_csv": root / "hourly_csv",
    }


def ensure_layout(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def day_token(day: date) -> str:
    return day.strftime("%Y-%m-%d")


def api_day_token(day: date) -> str:
    return day.strftime("%Y%m%d")


def daily_paths(paths: dict[str, Path], day: date) -> tuple[Path, Path]:
    year = str(day.year)
    return (
        paths["daily_raw"] / year / f"{day_token(day)}.json",
        paths["daily_csv"] / year / f"{day_token(day)}.csv",
    )


def day_already_collected(paths: dict[str, Path], day: date) -> bool:
    raw_path, csv_path = daily_paths(paths, day)
    return raw_path.exists() and csv_path.exists()


def request_day(config: dict, day: date) -> dict:
    request_config = config["request"]
    auth_env, auth_key, is_encoded_key = resolve_auth_key(config)

    params = {
        "pageNo": 1,
        "numOfRows": request_config.get("num_of_rows", 500),
        "dataType": request_config.get("data_type", "json"),
        "tradeYmd": api_day_token(day),
    }
    if not is_encoded_key:
        params["serviceKey"] = auth_key

    base_url = request_config["base_url"]
    if is_encoded_key:
        separator = "&" if "?" in base_url else "?"
        base_url = f"{base_url}{separator}serviceKey={auth_key}"

    retries = request_config.get("retries", 3)
    timeout = request_config.get("timeout_seconds", 30)
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(base_url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except HTTPError as error:
            if error.response is not None and error.response.status_code == 429 and attempt < retries:
                time.sleep(max(10, attempt * 10))
                continue
            raise
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
    raise RuntimeError("Unreachable retry state.")


def parse_response(payload: dict) -> tuple[pd.DataFrame, dict]:
    response = payload.get("response", {})
    header = response.get("header", {})
    body = response.get("body") or {}

    result_code = str(header.get("resultCode", ""))
    result_msg = header.get("resultMsg", "")
    if result_code and result_code != "00":
        raise RuntimeError(f"KPX solar API error: resultCode={result_code}, resultMsg={result_msg}")

    items = ((body.get("items") or {}).get("item")) or []
    if isinstance(items, dict):
        items = [items]

    frame = pd.DataFrame(items)
    if not frame.empty:
        frame = frame.rename(
            columns={
                "tradeNo": "hour_ending",
                "tradeYmd": "trade_date",
                "regionNm": "region",
                "amgo": "generation_mwh",
            }
        )
        frame["hour_ending"] = pd.to_numeric(frame["hour_ending"], errors="coerce").astype("Int64")
        frame["generation_mwh"] = pd.to_numeric(frame["generation_mwh"], errors="coerce")
        frame["generation_kw"] = frame["generation_mwh"] * 1000.0
        frame["timestamp"] = pd.to_datetime(frame["trade_date"], format="%Y%m%d") + pd.to_timedelta(
            frame["hour_ending"].astype(int),
            unit="h",
        )
        frame["fuel_type"] = "태양광"
        frame["source"] = "kpx_solar_api"
        frame = frame[
            [
                "timestamp",
                "trade_date",
                "hour_ending",
                "region",
                "fuel_type",
                "generation_mwh",
                "generation_kw",
                "source",
            ]
        ].sort_values(["timestamp", "region"])
    else:
        frame = pd.DataFrame(
            columns=[
                "timestamp",
                "trade_date",
                "hour_ending",
                "region",
                "fuel_type",
                "generation_mwh",
                "generation_kw",
                "source",
            ]
        )

    meta = {
        "result_code": result_code,
        "result_msg": result_msg,
        "total_count": int(body.get("totalCount") or 0),
        "num_of_rows": int(body.get("numOfRows") or 0),
        "page_no": int(body.get("pageNo") or 1),
    }
    return frame, meta


def write_day(paths: dict[str, Path], day: date, payload: dict, frame: pd.DataFrame, config: dict) -> None:
    raw_path, csv_path = daily_paths(paths, day)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    if config["storage"].get("save_raw_response", True):
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if config["storage"].get("save_daily_csv", True):
        frame.to_csv(csv_path, index=False, encoding="utf-8-sig")


def append_manifest(paths: dict[str, Path], payload: dict) -> None:
    manifest_path = paths["metadata"] / "daily_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_collection_config(paths: dict[str, Path], config: dict) -> None:
    auth_env, _, _ = resolve_auth_key(config)
    safe_config = json.loads(json.dumps(config, ensure_ascii=False, default=str))
    safe_config["request"]["resolved_auth_env"] = auth_env
    config_path = paths["metadata"] / "collection_config.json"
    config_path.write_text(json.dumps(safe_config, indent=2, ensure_ascii=False), encoding="utf-8")


def write_monthly_hourly(paths: dict[str, Path], collected_frames: list[pd.DataFrame], config: dict) -> None:
    if not collected_frames or not config["storage"].get("save_hourly_csv", True):
        return

    frame = pd.concat(collected_frames, ignore_index=True)
    if frame.empty or "timestamp" not in frame.columns:
        return
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    regions = set(config.get("filter", {}).get("regions") or [])
    if regions:
        frame = frame[frame["region"].isin(regions)].copy()

    for month, monthly_frame in frame.groupby(frame["timestamp"].dt.strftime("%Y-%m")):
        year = month[:4]
        monthly_path = paths["hourly_csv"] / year / f"{month}.csv"
        monthly_path.parent.mkdir(parents=True, exist_ok=True)
        if monthly_path.exists():
            existing = pd.read_csv(monthly_path)
            monthly_frame = pd.concat([existing, monthly_frame], ignore_index=True)
            monthly_frame = monthly_frame.drop_duplicates(subset=["timestamp", "region"], keep="last")
        monthly_frame = monthly_frame.sort_values(["timestamp", "region"])
        monthly_frame.to_csv(monthly_path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    config = apply_args(config, args)
    load_env_file(config)

    paths = build_paths(config)
    ensure_layout(paths)
    write_collection_config(paths, config)

    max_requests = int(config["range"].get("max_requests") or 0)
    made_requests = 0
    collected_frames: list[pd.DataFrame] = []

    for day in date_range(config["range"]["start_date"], config["range"]["end_date"]):
        if day_already_collected(paths, day):
            print(f"Skip already collected day: {day_token(day)}")
            _, csv_path = daily_paths(paths, day)
            try:
                existing_frame = pd.read_csv(csv_path)
                if not existing_frame.empty:
                    collected_frames.append(existing_frame)
            except EmptyDataError:
                pass
            continue
        if max_requests and made_requests >= max_requests:
            print(f"Stop: reached max_requests={max_requests}")
            break

        started_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        try:
            payload = request_day(config, day)
        except HTTPError as error:
            if error.response is not None and error.response.status_code == 429:
                print(f"Stop: API rate limit reached at {day_token(day)}")
                break
            raise
        frame, meta = parse_response(payload)
        write_day(paths, day, payload, frame, config)
        collected_frames.append(frame)
        made_requests += 1

        append_manifest(
            paths,
            {
                "date": day_token(day),
                "region_slug": config["region_slug"],
                "rows": int(len(frame)),
                "requests": 1,
                "total_count": meta["total_count"],
                "started_at": started_at,
                "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
        )
        print(f"Collected {day_token(day)} rows={len(frame)} requests={made_requests}")
        time.sleep(config["request"].get("sleep_seconds", 0.2))

    write_monthly_hourly(paths, collected_frames, config)


if __name__ == "__main__":
    main()
