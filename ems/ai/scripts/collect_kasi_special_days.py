from __future__ import annotations

import argparse
import csv
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect KASI special-day calendar data.")
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/kasi_special_days_example.yaml",
        help="Path to YAML config.",
    )
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_env_file(config: dict[str, Any]) -> None:
    env_file = config.get("request", {}).get("env_file")
    if not env_file:
        return
    if load_dotenv:
        load_dotenv(env_file)
        return

    path = Path(env_file)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def resolve_auth_key(config: dict[str, Any]) -> tuple[str, str]:
    request_config = config["request"]
    candidates = request_config.get("auth_env_candidates") or []
    if request_config.get("auth_env"):
        candidates = [request_config["auth_env"], *candidates]

    for env_name in candidates:
        auth_key = os.environ.get(env_name)
        if auth_key:
            return env_name, auth_key
    raise RuntimeError(f"No auth key found. Checked: {', '.join(candidates)}")


def year_range(config: dict[str, Any]) -> list[int]:
    start_year = int(config["range"]["start_year"])
    end_year = int(config["range"]["end_year"])
    return list(range(start_year, end_year + 1))


def build_paths(config: dict[str, Any]) -> dict[str, Path]:
    raw_root = Path(config["storage"]["raw_root"])
    return {
        "raw_root": raw_root,
        "metadata": raw_root / "metadata",
        "processed": Path(config["storage"]["processed_path"]),
    }


def ensure_layout(paths: dict[str, Path]) -> None:
    paths["raw_root"].mkdir(parents=True, exist_ok=True)
    paths["metadata"].mkdir(parents=True, exist_ok=True)
    paths["processed"].parent.mkdir(parents=True, exist_ok=True)


def request_special_days(config: dict[str, Any], endpoint: str, year: int, auth_key: str) -> str:
    request_config = config["request"]
    url = f"{request_config['base_url'].rstrip('/')}/{endpoint}"
    params = {
        "serviceKey": auth_key,
        "solYear": str(year),
        "numOfRows": int(request_config.get("num_of_rows", 100)),
        "pageNo": 1,
    }

    retries = int(request_config.get("retries", 3))
    timeout = int(request_config.get("timeout_seconds", 30))
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            if not response.text.strip():
                raise RuntimeError("Empty response body.")
            return response.text
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(2 * attempt, 5))
    raise RuntimeError("Unreachable retry state.")


def xml_text(element: ET.Element, name: str) -> str:
    child = element.find(name)
    return "" if child is None or child.text is None else child.text.strip()


def parse_header(root: ET.Element) -> tuple[str, str]:
    result_code = xml_text(root, ".//resultCode")
    result_msg = xml_text(root, ".//resultMsg")
    if not result_code:
        result_code = xml_text(root, ".//returnReasonCode")
    if not result_msg:
        result_msg = xml_text(root, ".//returnAuthMsg")
    return result_code, result_msg


def parse_locdate(locdate: str) -> str:
    if not locdate:
        return ""
    try:
        return datetime.strptime(locdate, "%Y%m%d").date().isoformat()
    except ValueError:
        return ""


def parse_items(raw_xml: str, endpoint_config: dict[str, Any], year: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = ET.fromstring(raw_xml)
    result_code, result_msg = parse_header(root)
    if result_code and result_code not in {"00", "0"}:
        raise RuntimeError(
            f"KASI API error: endpoint={endpoint_config['path']}, year={year}, "
            f"resultCode={result_code}, resultMsg={result_msg}"
        )

    rows: list[dict[str, Any]] = []
    for item in root.findall(".//item"):
        locdate = xml_text(item, "locdate")
        name = xml_text(item, "dateName")
        category = endpoint_config["category"]
        is_holiday = xml_text(item, "isHoliday").upper() == "Y"
        if category == "holiday":
            is_holiday = True if not xml_text(item, "isHoliday") else is_holiday

        rows.append(
            {
                "date": parse_locdate(locdate),
                "name": name,
                "category": category,
                "is_holiday": is_holiday,
                "is_solar_term": category == "solar_term",
                "source": "kasi_spcde_info",
                "endpoint": endpoint_config["path"],
                "year": year,
                "seq": xml_text(item, "seq"),
                "locdate": locdate,
            }
        )

    meta = {
        "result_code": result_code,
        "result_msg": result_msg,
        "total_count": int(xml_text(root, ".//totalCount") or 0),
        "num_of_rows": int(xml_text(root, ".//numOfRows") or 0),
        "page_no": int(xml_text(root, ".//pageNo") or 1),
    }
    return rows, meta


def raw_path(paths: dict[str, Path], year: int, endpoint: str) -> Path:
    return paths["raw_root"] / str(year) / f"{endpoint}.xml"


def write_raw(paths: dict[str, Path], year: int, endpoint: str, raw_xml: str) -> None:
    path = raw_path(paths, year, endpoint)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw_xml, encoding="utf-8")


def append_manifest(paths: dict[str, Path], payload: dict[str, Any]) -> None:
    manifest_path = paths["metadata"] / "collection_manifest.jsonl"
    with manifest_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_collection_config(paths: dict[str, Path], config: dict[str, Any], auth_env: str) -> None:
    safe_config = json.loads(json.dumps(config, ensure_ascii=False))
    safe_config["request"]["resolved_auth_env"] = auth_env
    config_path = paths["metadata"] / "collection_config.json"
    config_path.write_text(json.dumps(safe_config, indent=2, ensure_ascii=False), encoding="utf-8")


def utc_now_token() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_processed(paths: dict[str, Path], row_groups: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    columns = [
        "date",
        "name",
        "category",
        "is_holiday",
        "is_solar_term",
        "source",
        "endpoint",
        "year",
        "seq",
        "locdate",
    ]
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for rows in row_groups:
        for row in rows:
            key = (str(row["date"]), str(row["name"]), str(row["category"]))
            deduped[key] = row

    combined = sorted(deduped.values(), key=lambda row: (row["date"], row["category"], row["name"]))
    with paths["processed"].open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(combined)
    return combined


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env_file(config)
    auth_env, auth_key = resolve_auth_key(config)

    paths = build_paths(config)
    ensure_layout(paths)
    write_collection_config(paths, config, auth_env)

    row_groups: list[list[dict[str, Any]]] = []
    for year in year_range(config):
        for endpoint_config in config["endpoints"]:
            endpoint = endpoint_config["path"]
            started_at = utc_now_token()
            raw_xml = request_special_days(config, endpoint, year, auth_key)
            rows, meta = parse_items(raw_xml, endpoint_config, year)
            if config["storage"].get("save_raw_response", True):
                write_raw(paths, year, endpoint, raw_xml)
            row_groups.append(rows)
            append_manifest(
                paths,
                {
                    "year": year,
                    "endpoint": endpoint,
                    "category": endpoint_config["category"],
                    "rows": int(len(rows)),
                    "total_count": meta["total_count"],
                    "result_code": meta["result_code"],
                    "result_msg": meta["result_msg"],
                    "started_at": started_at,
                    "saved_at": utc_now_token(),
                },
            )
            print(f"Collected {endpoint} {year}: rows={len(rows)}")
            time.sleep(float(config["request"].get("sleep_seconds", 0.3)))

    processed = write_processed(paths, row_groups)
    print(f"Wrote {paths['processed']} rows={len(processed)}")


if __name__ == "__main__":
    main()
