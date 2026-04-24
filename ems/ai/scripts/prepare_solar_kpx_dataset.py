from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT = "G:/내 드라이브/s305-ai-data/processed/merged/jeonnam_station_165_hourly.csv"
DEFAULT_FEATURES_OUTPUT = "G:/내 드라이브/s305-ai-data/processed/features/solar_kpx_2025_hourly.csv"
DEFAULT_TRAIN_OUTPUT = "G:/내 드라이브/s305-ai-data/processed/splits/solar_kpx_train.csv"
DEFAULT_VAL_OUTPUT = "G:/내 드라이브/s305-ai-data/processed/splits/solar_kpx_val.csv"

SENTINEL_COLUMNS = ["kma_ta", "kma_hm", "kma_ca_tot", "kma_si", "kma_rn", "kma_ws", "kma_ss", "kma_pa", "kma_ps"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare train/val CSVs for solar forecasting from merged KMA + KPX hourly data."
    )
    parser.add_argument("--input", default=DEFAULT_INPUT, help="Path to merged hourly CSV.")
    parser.add_argument("--features-output", default=DEFAULT_FEATURES_OUTPUT, help="Path to write feature CSV.")
    parser.add_argument("--train-output", default=DEFAULT_TRAIN_OUTPUT, help="Path to write train CSV.")
    parser.add_argument("--val-output", default=DEFAULT_VAL_OUTPUT, help="Path to write validation CSV.")
    parser.add_argument(
        "--val-start",
        default="2025-11-01 00:00:00",
        help="Validation split start timestamp in local naive time.",
    )
    return parser.parse_args()


def ensure_parent(path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def replace_sentinels(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column not in frame.columns:
            continue
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame.loc[frame[column] <= -9, column] = np.nan
    return frame


def add_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    hours = frame["timestamp"].dt.hour
    day_of_year = frame["timestamp"].dt.dayofyear
    frame["hour_of_day_sin"] = np.sin(2 * np.pi * hours / 24.0)
    frame["hour_of_day_cos"] = np.cos(2 * np.pi * hours / 24.0)
    frame["day_of_year_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    frame["day_of_year_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)
    return frame


def build_dataset(input_path: str | Path, val_start: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = pd.read_csv(input_path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])

    frame = frame[(frame["timestamp"] >= pd.Timestamp("2025-01-01 00:00:00"))].copy()
    frame = frame[frame["kpx_generation_kw"].notna()].copy()
    frame = frame.sort_values("timestamp").reset_index(drop=True)

    frame = replace_sentinels(frame, SENTINEL_COLUMNS)
    frame["generation_kw"] = pd.to_numeric(frame["kpx_generation_kw"], errors="coerce")
    frame["temperature"] = frame["kma_ta"]
    frame["humidity"] = frame["kma_hm"]
    frame["cloud_cover"] = frame["kma_ca_tot"]
    frame["irradiance"] = frame["kma_si"]
    frame["rainfall_mm"] = frame["kma_rn"]
    frame["wind_speed"] = frame["kma_ws"]

    # Time interpolation is enough for hourly weather continuity here.
    weather_columns = ["temperature", "humidity", "cloud_cover", "irradiance", "rainfall_mm", "wind_speed"]
    frame[weather_columns] = frame[weather_columns].interpolate(limit_direction="both")
    frame[weather_columns] = frame[weather_columns].ffill().bfill()

    frame["past_solar_P_kw"] = frame["generation_kw"]
    frame["past_solar_P_kw_lag_1"] = frame["generation_kw"].shift(1)
    frame["past_solar_P_kw_lag_24"] = frame["generation_kw"].shift(24)
    frame["rolling_mean_3h"] = frame["generation_kw"].rolling(window=3, min_periods=1).mean()
    frame["rolling_mean_24h"] = frame["generation_kw"].rolling(window=24, min_periods=1).mean()
    frame["future_solar_P_kw"] = frame["generation_kw"].shift(-1)
    frame["future_solar_P_kw_6h"] = frame["generation_kw"].shift(-6)
    frame["future_solar_P_kw_24h"] = frame["generation_kw"].shift(-24)

    frame = add_time_features(frame)
    frame["data_source"] = "kma_kpx_2025"

    dataset = frame[
        [
            "timestamp",
            "station_id",
            "data_source",
            "past_solar_P_kw",
            "past_solar_P_kw_lag_1",
            "past_solar_P_kw_lag_24",
            "rolling_mean_3h",
            "rolling_mean_24h",
            "temperature",
            "humidity",
            "cloud_cover",
            "irradiance",
            "rainfall_mm",
            "wind_speed",
            "hour_of_day_sin",
            "hour_of_day_cos",
            "day_of_year_sin",
            "day_of_year_cos",
            "future_solar_P_kw",
            "future_solar_P_kw_6h",
            "future_solar_P_kw_24h",
        ]
    ].copy()

    dataset = dataset.dropna().reset_index(drop=True)

    val_boundary = pd.Timestamp(val_start)
    train = dataset[dataset["timestamp"] < val_boundary].reset_index(drop=True)
    val = dataset[dataset["timestamp"] >= val_boundary].reset_index(drop=True)
    return dataset, train, val


def write_manifest(features_path: Path, dataset: pd.DataFrame, train: pd.DataFrame, val: pd.DataFrame, val_start: str) -> None:
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "features_path": str(features_path),
        "rows_total": int(len(dataset)),
        "rows_train": int(len(train)),
        "rows_val": int(len(val)),
        "columns": list(dataset.columns),
        "min_timestamp": dataset["timestamp"].min().isoformat() if not dataset.empty else None,
        "max_timestamp": dataset["timestamp"].max().isoformat() if not dataset.empty else None,
        "val_start": val_start,
    }
    manifest_path = features_path.parent / f"{features_path.stem}_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    args = parse_args()
    dataset, train, val = build_dataset(args.input, args.val_start)

    features_output = ensure_parent(args.features_output)
    train_output = ensure_parent(args.train_output)
    val_output = ensure_parent(args.val_output)

    dataset.to_csv(features_output, index=False, encoding="utf-8-sig")
    train.to_csv(train_output, index=False, encoding="utf-8-sig")
    val.to_csv(val_output, index=False, encoding="utf-8-sig")
    write_manifest(features_output, dataset, train, val, args.val_start)

    print(f"Features file: {features_output}")
    print(f"Train rows: {len(train)}")
    print(f"Val rows: {len(val)}")


if __name__ == "__main__":
    main()
