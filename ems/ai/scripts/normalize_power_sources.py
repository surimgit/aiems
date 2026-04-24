from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_KEPCO_INPUT = (
    "G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/downloads/"
    "한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231.csv"
)
DEFAULT_KEPCO_OUTPUT = (
    "G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/normalized/kepco_jeonnam_hourly.csv"
)
DEFAULT_WEST_POWER_INPUT = (
    "G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/downloads/"
    "한국서부발전(주)_태양광 발전 현황_20230630.csv"
)
DEFAULT_WEST_POWER_OUTPUT = (
    "G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/normalized/west_power_hourly.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize KPX and West Power solar CSV files into hourly long-format CSVs."
    )
    parser.add_argument("--kepco-input", default=DEFAULT_KEPCO_INPUT, help="Path to raw KPX CSV.")
    parser.add_argument(
        "--kepco-output",
        default=DEFAULT_KEPCO_OUTPUT,
        help="Path to write normalized KPX CSV.",
    )
    parser.add_argument(
        "--kepco-region",
        default="전라남도",
        help="Region name to keep from the KPX CSV.",
    )
    parser.add_argument(
        "--kepco-fuel",
        default="태양광",
        help="Fuel type to keep from the KPX CSV.",
    )
    parser.add_argument(
        "--west-power-input",
        default=DEFAULT_WEST_POWER_INPUT,
        help="Path to raw West Power CSV.",
    )
    parser.add_argument(
        "--west-power-output",
        default=DEFAULT_WEST_POWER_OUTPUT,
        help="Path to write normalized West Power CSV.",
    )
    return parser.parse_args()


def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="cp949")


def ensure_parent(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def parse_hour_ending(value: object) -> int:
    text = str(value).strip().replace("시", "")
    hour = int(text)
    if hour < 1 or hour > 24:
        raise ValueError(f"Unsupported hour value: {value}")
    return hour


def hour_ending_to_timestamp(date_series: pd.Series, hour_series: pd.Series) -> pd.Series:
    base_dates = pd.to_datetime(date_series, format="%Y-%m-%d")
    hour_offsets = hour_series.astype(int)
    return base_dates + pd.to_timedelta(hour_offsets, unit="h")


def normalize_kepco(input_path: str | Path, output_path: str | Path, region: str, fuel: str) -> dict:
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

    frame["region"] = frame["region"].astype(str).str.strip()
    frame["fuel_type"] = frame["fuel_type"].astype(str).str.strip()
    frame = frame[(frame["region"] == region) & (frame["fuel_type"] == fuel)].copy()

    frame["hour_ending"] = frame["hour_ending"].apply(parse_hour_ending)
    frame["timestamp"] = hour_ending_to_timestamp(frame["trade_date"], frame["hour_ending"])
    frame["generation_mwh"] = pd.to_numeric(frame["generation_mwh"], errors="coerce")
    frame["generation_kw"] = frame["generation_mwh"] * 1000.0
    frame["source"] = "kpx"

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

    output_file = ensure_parent(output_path)
    normalized.to_csv(output_file, index=False, encoding="utf-8-sig")

    return {
        "input_path": str(input_path),
        "output_path": str(output_file),
        "rows": int(len(normalized)),
        "columns": list(normalized.columns),
        "region": region,
        "fuel_type": fuel,
        "min_timestamp": normalized["timestamp"].min().isoformat() if not normalized.empty else None,
        "max_timestamp": normalized["timestamp"].max().isoformat() if not normalized.empty else None,
    }


def normalize_west_power(input_path: str | Path, output_path: str | Path) -> dict:
    frame = read_csv(input_path)
    hour_columns = [f"{hour:02d}시" for hour in range(1, 25)]
    missing_columns = [column for column in hour_columns if column not in frame.columns]
    if missing_columns:
        raise ValueError(f"Missing hourly columns: {missing_columns}")

    frame = frame.rename(
        columns={
            "발전기명": "generator_name",
            "년월일": "date",
            "설비용량(MW)": "installed_capacity_mw",
        }
    )

    melted = frame.melt(
        id_vars=["generator_name", "date", "installed_capacity_mw"],
        value_vars=hour_columns,
        var_name="hour_ending",
        value_name="generation_wh",
    )

    melted["hour_ending"] = melted["hour_ending"].apply(parse_hour_ending)
    melted["timestamp"] = hour_ending_to_timestamp(melted["date"], melted["hour_ending"])
    melted["installed_capacity_mw"] = pd.to_numeric(melted["installed_capacity_mw"], errors="coerce")
    melted["generation_wh"] = pd.to_numeric(melted["generation_wh"], errors="coerce")
    melted["installed_capacity_kw"] = melted["installed_capacity_mw"] * 1000.0
    melted["generation_kwh"] = melted["generation_wh"] / 1000.0
    melted["generation_kw"] = melted["generation_kwh"]
    melted["capacity_factor"] = (
        melted["generation_kw"] / melted["installed_capacity_kw"]
    ).where(melted["installed_capacity_kw"] > 0)
    melted["source"] = "west_power"

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

    output_file = ensure_parent(output_path)
    normalized.to_csv(output_file, index=False, encoding="utf-8-sig")

    return {
        "input_path": str(input_path),
        "output_path": str(output_file),
        "rows": int(len(normalized)),
        "columns": list(normalized.columns),
        "min_timestamp": normalized["timestamp"].min().isoformat() if not normalized.empty else None,
        "max_timestamp": normalized["timestamp"].max().isoformat() if not normalized.empty else None,
        "generator_count": int(normalized["generator_name"].nunique()) if not normalized.empty else 0,
    }


def write_manifest(output_path: str | Path, payload: dict) -> Path:
    output_file = Path(output_path)
    manifest_path = output_file.parent / f"{output_file.stem}_manifest.json"
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **payload,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def main() -> None:
    args = parse_args()

    kepco_summary = normalize_kepco(
        input_path=args.kepco_input,
        output_path=args.kepco_output,
        region=args.kepco_region,
        fuel=args.kepco_fuel,
    )
    west_power_summary = normalize_west_power(
        input_path=args.west_power_input,
        output_path=args.west_power_output,
    )

    kepco_manifest = write_manifest(args.kepco_output, kepco_summary)
    west_power_manifest = write_manifest(args.west_power_output, west_power_summary)

    print(f"Normalized KPX file: {args.kepco_output}")
    print(f"KPX manifest: {kepco_manifest}")
    print(f"KPX rows: {kepco_summary['rows']}")
    print(f"Normalized West Power file: {args.west_power_output}")
    print(f"West Power manifest: {west_power_manifest}")
    print(f"West Power rows: {west_power_summary['rows']}")


if __name__ == "__main__":
    main()
