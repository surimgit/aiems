from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_KMA_GLOB = "G:/내 드라이브/s305-ai-data/raw/kma_asos/jeonnam/station_165/hourly_csv/*/*.csv"
DEFAULT_KPX_INPUT = "G:/내 드라이브/s305-ai-data/raw/kepco/jeonnam/normalized/kepco_jeonnam_hourly.csv"
DEFAULT_WEST_INPUT = (
    "G:/내 드라이브/s305-ai-data/raw/west_power/jeonnam/normalized/west_power_hourly.csv"
)
DEFAULT_OUTPUT = "G:/내 드라이브/s305-ai-data/processed/merged/jeonnam_station_165_hourly.csv"
DEFAULT_WEST_KEYWORDS = "영암,목포,무안,해남,신안,전남"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge KMA hourly weather with KPX and West Power normalized hourly datasets."
    )
    parser.add_argument("--kma-glob", default=DEFAULT_KMA_GLOB, help="Glob pattern for KMA hourly CSV files.")
    parser.add_argument("--kpx-input", default=DEFAULT_KPX_INPUT, help="Path to normalized KPX CSV.")
    parser.add_argument("--west-input", default=DEFAULT_WEST_INPUT, help="Path to normalized West Power CSV.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write merged CSV.")
    parser.add_argument(
        "--west-keywords",
        default=DEFAULT_WEST_KEYWORDS,
        help="Comma-separated keywords used to filter West Power generator names before hourly aggregation.",
    )
    return parser.parse_args()


def ensure_parent(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def load_kma_frame(kma_glob: str) -> pd.DataFrame:
    files = [Path(path) for path in sorted(glob.glob(kma_glob))]
    if not files:
        raise FileNotFoundError(f"No KMA CSV files matched glob: {kma_glob}")

    frames = [pd.read_csv(file) for file in files]
    frame = pd.concat(frames, ignore_index=True)
    frame["timestamp"] = pd.to_datetime(frame["TM"].astype(str), format="%Y%m%d%H%M")

    selected_columns = {
        "timestamp": "timestamp",
        "STN": "station_id",
        "TA": "kma_ta",
        "HM": "kma_hm",
        "CA_TOT": "kma_ca_tot",
        "SI": "kma_si",
        "RN": "kma_rn",
        "WS": "kma_ws",
        "WD": "kma_wd",
        "SS": "kma_ss",
        "PA": "kma_pa",
        "PS": "kma_ps",
    }

    normalized = frame[list(selected_columns.keys())].rename(columns=selected_columns)
    numeric_columns = [column for column in normalized.columns if column not in {"timestamp"}]
    for column in numeric_columns:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    return normalized


def load_kpx_frame(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])

    normalized = frame.rename(
        columns={
            "generation_kw": "kpx_generation_kw",
            "generation_mwh": "kpx_generation_mwh",
            "region": "kpx_region",
            "fuel_type": "kpx_fuel_type",
        }
    )[
        ["timestamp", "kpx_region", "kpx_fuel_type", "kpx_generation_mwh", "kpx_generation_kw"]
    ]
    return normalized.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)


def load_west_frame(path: str | Path, keywords: list[str]) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])

    filtered = frame.copy()
    if keywords:
        pattern = "|".join(keywords)
        filtered = frame[frame["generator_name"].astype(str).str.contains(pattern, regex=True, na=False)].copy()

    if filtered.empty:
        aggregated = pd.DataFrame(
            columns=[
                "timestamp",
                "west_generation_kw",
                "west_installed_capacity_kw",
                "west_capacity_factor",
                "west_generator_count",
            ]
        )
    else:
        aggregated = (
            filtered.groupby("timestamp", as_index=False)
            .agg(
                west_generation_kw=("generation_kw", "sum"),
                west_installed_capacity_kw=("installed_capacity_kw", "sum"),
                west_generator_count=("generator_name", "nunique"),
            )
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        aggregated["west_capacity_factor"] = (
            aggregated["west_generation_kw"] / aggregated["west_installed_capacity_kw"]
        ).where(aggregated["west_installed_capacity_kw"] > 0)
        aggregated = aggregated[
            [
                "timestamp",
                "west_generation_kw",
                "west_installed_capacity_kw",
                "west_capacity_factor",
                "west_generator_count",
            ]
        ]

    details = {
        "west_keywords": keywords,
        "west_total_rows": int(len(frame)),
        "west_filtered_rows": int(len(filtered)),
        "west_total_generators": int(frame["generator_name"].nunique()),
        "west_filtered_generators": int(filtered["generator_name"].nunique()) if not filtered.empty else 0,
        "west_filtered_generator_names": (
            sorted(filtered["generator_name"].dropna().astype(str).unique().tolist()) if not filtered.empty else []
        ),
    }
    return aggregated, details


def build_summary(merged: pd.DataFrame, kma: pd.DataFrame, kpx: pd.DataFrame, west: pd.DataFrame, west_details: dict) -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": int(len(merged)),
        "columns": list(merged.columns),
        "kma_rows": int(len(kma)),
        "kpx_rows": int(len(kpx)),
        "west_rows": int(len(west)),
        "kma_min_timestamp": kma["timestamp"].min().isoformat() if not kma.empty else None,
        "kma_max_timestamp": kma["timestamp"].max().isoformat() if not kma.empty else None,
        "kpx_min_timestamp": kpx["timestamp"].min().isoformat() if not kpx.empty else None,
        "kpx_max_timestamp": kpx["timestamp"].max().isoformat() if not kpx.empty else None,
        "west_min_timestamp": west["timestamp"].min().isoformat() if not west.empty else None,
        "west_max_timestamp": west["timestamp"].max().isoformat() if not west.empty else None,
        "kpx_overlap_rows": int(merged["kpx_generation_kw"].notna().sum()),
        "west_overlap_rows": int(merged["west_generation_kw"].notna().sum()),
        **west_details,
    }


def main() -> None:
    args = parse_args()
    west_keywords = [keyword.strip() for keyword in args.west_keywords.split(",") if keyword.strip()]

    kma = load_kma_frame(args.kma_glob)
    kpx = load_kpx_frame(args.kpx_input)
    west, west_details = load_west_frame(args.west_input, west_keywords)

    merged = kma.merge(kpx, on="timestamp", how="left").merge(west, on="timestamp", how="left")
    merged = merged.sort_values("timestamp").reset_index(drop=True)

    output_path = ensure_parent(args.output)
    merged.to_csv(output_path, index=False, encoding="utf-8-sig")

    summary = build_summary(merged, kma, kpx, west, west_details)
    manifest_path = output_path.parent / f"{output_path.stem}_manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Merged file: {output_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Rows: {summary['rows']}")
    print(f"KPX overlap rows: {summary['kpx_overlap_rows']}")
    print(f"West overlap rows: {summary['west_overlap_rows']}")


if __name__ == "__main__":
    main()
