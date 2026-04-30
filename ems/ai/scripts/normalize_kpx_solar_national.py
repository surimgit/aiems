from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = (
    "G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/downloads/"
    "한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231.csv"
)
DEFAULT_OUTPUT = "G:/내 드라이브/s305-ai-data/processed/solar/kpx_solar_by_region_hourly_2025.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize national KPX regional hourly solar CSV.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to raw KPX solar/wind CSV.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write normalized solar CSV.")
    parser.add_argument("--fuel", default="태양광", help="Fuel type to keep.")
    return parser.parse_args()


def read_csv(path: str | Path) -> pd.DataFrame:
    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def parse_hour_ending(value: object) -> int:
    text = str(value).strip().replace("시", "")
    hour = int(text)
    if hour < 1 or hour > 24:
        raise ValueError(f"Unsupported hour value: {value}")
    return hour


def hour_ending_to_timestamp(date_series: pd.Series, hour_series: pd.Series) -> pd.Series:
    base_dates = pd.to_datetime(date_series, format="%Y-%m-%d")
    return base_dates + pd.to_timedelta(hour_series.astype(int), unit="h")


def normalize(input_path: str | Path, output_path: str | Path, fuel: str) -> dict:
    frame = read_csv(input_path)
    frame = frame.rename(
        columns={
            "거래일": "trade_date",
            "거래시간": "hour_ending",
            "지역": "region",
            "연료원": "fuel_type",
            "전력거래량(MWh)": "generation_mwh",
        }
    )

    required = {"trade_date", "hour_ending", "region", "fuel_type", "generation_mwh"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns after rename: {sorted(missing)}")

    frame["region"] = frame["region"].astype(str).str.strip()
    frame["fuel_type"] = frame["fuel_type"].astype(str).str.strip()
    frame = frame[frame["fuel_type"] == fuel].copy()

    frame["hour_ending"] = frame["hour_ending"].apply(parse_hour_ending)
    frame["timestamp"] = hour_ending_to_timestamp(frame["trade_date"], frame["hour_ending"])
    frame["generation_mwh"] = pd.to_numeric(frame["generation_mwh"], errors="coerce")
    frame["generation_kw"] = frame["generation_mwh"] * 1000.0
    frame["source"] = "kpx_solar_wind_by_region_file"

    normalized = frame[
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
    ].sort_values(["timestamp", "region"]).reset_index(drop=True)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    normalized.to_csv(output_file, index=False, encoding="utf-8-sig")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "output_path": str(output_file),
        "rows": int(len(normalized)),
        "columns": list(normalized.columns),
        "fuel_type": fuel,
        "region_count": int(normalized["region"].nunique()) if not normalized.empty else 0,
        "regions": sorted(normalized["region"].dropna().unique().tolist()) if not normalized.empty else [],
        "min_timestamp": normalized["timestamp"].min().isoformat() if not normalized.empty else None,
        "max_timestamp": normalized["timestamp"].max().isoformat() if not normalized.empty else None,
        "rows_by_region": {
            str(region): int(count)
            for region, count in normalized.groupby("region", dropna=False).size().sort_index().items()
        },
    }
    manifest_path = output_file.parent / f"{output_file.stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    args = parse_args()
    manifest = normalize(args.input, args.output, args.fuel)
    print(f"Normalized national KPX solar file: {manifest['output_path']}")
    print(f"Rows: {manifest['rows']}")
    print(f"Regions: {manifest['region_count']}")
    print(f"Period: {manifest['min_timestamp']} ~ {manifest['max_timestamp']}")


if __name__ == "__main__":
    main()
