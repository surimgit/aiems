from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge KPX capacity-factor features with KMA ASOS hourly weather.")
    parser.add_argument("--config", default="ems/ai/configs/merge/kpx_capacity_factor_with_asos.yaml")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def read_csv_any(path: str | Path) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def asos_csv_files(raw_root: Path, region_slug: str, station_id: int | str) -> list[Path]:
    root = raw_root / region_slug / f"station_{station_id}" / "hourly_csv"
    if not root.exists():
        raise FileNotFoundError(f"ASOS hourly CSV directory not found: {root}")
    files = sorted(root.glob("*/*.csv"))
    if not files:
        raise FileNotFoundError(f"No ASOS hourly CSV files found: {root}")
    return files


def clean_missing_values(
    frame: pd.DataFrame,
    columns: list[str],
    zero_if_negative_columns: set[str],
) -> pd.DataFrame:
    cleaned = frame.copy()
    for column in columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
        if column in zero_if_negative_columns:
            cleaned.loc[cleaned[column] < 0, column] = 0.0
        else:
            cleaned.loc[cleaned[column] <= -9, column] = pd.NA
    return cleaned


def load_asos_region(raw_root: Path, region_config: dict[str, Any], asos_config: dict[str, Any]) -> pd.DataFrame:
    weather_columns = dict(asos_config["weather_columns"])
    files = asos_csv_files(raw_root, region_config["region_slug"], region_config["station_id"])
    frames = [read_csv_any(path) for path in files]
    frame = pd.concat(frames, ignore_index=True)
    required = ["TM", *weather_columns.keys()]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing ASOS columns for {region_config['region']}: {missing}")

    zero_if_negative_columns = set(asos_config.get("zero_if_negative_columns", []))
    frame = clean_missing_values(frame[required], list(weather_columns.keys()), zero_if_negative_columns)
    frame["timestamp"] = pd.to_datetime(frame["TM"].astype(str), format="%Y%m%d%H%M", errors="coerce")
    frame["region"] = region_config["region"]
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")

    fill_columns = [column for column in asos_config.get("forward_fill_columns", []) if column in frame.columns]
    fill_limit = int(asos_config.get("forward_fill_limit_hours", 0))
    if fill_columns and fill_limit > 0:
        frame[fill_columns] = frame[fill_columns].ffill(limit=fill_limit)

    frame = frame.dropna(subset=["timestamp"]).rename(columns=weather_columns)
    selected = ["region", "timestamp", *weather_columns.values()]
    return frame[selected].drop_duplicates(["region", "timestamp"]).sort_values(["region", "timestamp"])


def load_asos(config: dict[str, Any]) -> pd.DataFrame:
    asos = config["asos"]
    raw_root = Path(asos["raw_root"])
    frames = [load_asos_region(raw_root, region, asos) for region in asos["regions"]]
    return pd.concat(frames, ignore_index=True).sort_values(["region", "timestamp"])


def merge_dataset(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    kpx = read_csv_any(config["kpx_features_path"])
    kpx["timestamp"] = pd.to_datetime(kpx["timestamp"], errors="coerce")
    kpx = kpx.dropna(subset=["timestamp", "region"]).copy()

    asos = load_asos(config)
    merged = kpx.merge(asos, on=["region", "timestamp"], how="left", validate="many_to_one")
    weather_columns = list(config["asos"]["weather_columns"].values())
    matched_rows = int(merged[weather_columns].notna().any(axis=1).sum())
    missing_by_column = {column: int(merged[column].isna().sum()) for column in weather_columns}

    summary = {
        "kpx_rows": int(len(kpx)),
        "asos_rows": int(len(asos)),
        "merged_rows": int(len(merged)),
        "weather_matched_rows": matched_rows,
        "weather_matched_ratio": float(matched_rows / len(merged)) if len(merged) else 0.0,
        "missing_by_weather_column": missing_by_column,
        "regions": sorted(merged["region"].dropna().unique().tolist()),
        "min_timestamp": merged["timestamp"].min().isoformat() if not merged.empty else None,
        "max_timestamp": merged["timestamp"].max().isoformat() if not merged.empty else None,
    }
    return merged, summary


def write_outputs(config: dict[str, Any], merged: pd.DataFrame, summary: dict[str, Any]) -> dict[str, Any]:
    output_root = Path(config["output_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    val_start = pd.Timestamp(config["val_start"])

    train = merged[merged["timestamp"] < val_start].copy()
    val = merged[merged["timestamp"] >= val_start].copy()

    features_path = output_root / "kpx_5min_capacity_factor_with_asos_features.csv"
    train_path = output_root / "kpx_5min_capacity_factor_with_asos_train.csv"
    val_path = output_root / "kpx_5min_capacity_factor_with_asos_val.csv"
    manifest_path = output_root / "kpx_5min_capacity_factor_with_asos_manifest.json"

    merged.to_csv(features_path, index=False, encoding="utf-8-sig")
    train.to_csv(train_path, index=False, encoding="utf-8-sig")
    val.to_csv(val_path, index=False, encoding="utf-8-sig")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": config,
        "features_path": str(features_path),
        "train_path": str(train_path),
        "val_path": str(val_path),
        "rows_train": int(len(train)),
        "rows_val": int(len(val)),
        "columns": list(merged.columns),
        **summary,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    merged, summary = merge_dataset(config)
    manifest = write_outputs(config, merged, summary)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
