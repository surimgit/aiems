from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from astral import Observer
from astral.sun import elevation


DEFAULT_INPUT = r"C:\Users\SSAFY\Downloads\한국전력거래소_지역별 5분단위 태양광 계량데이터_20251231.csv"
DEFAULT_OUTPUT_ROOT = Path("ems/ai/data/processed/kpx_5min_capacity_factor")
DEFAULT_REGIONS = "서울시,대전시"
REGION_COORDS = {
    "서울시": (37.5665, 126.9780),
    "대전시": (36.3504, 127.3845),
}
TIMEZONE = ZoneInfo("Asia/Seoul")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare clean KPX 5-minute solar capacity-factor training splits.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--regions", default=DEFAULT_REGIONS)
    parser.add_argument("--val-start", default="2025-11-01 00:00:00")
    parser.add_argument("--capacity-quantile", type=float, default=0.999)
    parser.add_argument("--night-threshold-wh", type=float, default=1000.0)
    return parser.parse_args()


def read_csv_any(path: str | Path) -> pd.DataFrame:
    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(path)


def solar_elevation(region: str, timestamp: pd.Timestamp) -> float:
    latitude, longitude = REGION_COORDS[region]
    observer = Observer(latitude=latitude, longitude=longitude)
    return float(elevation(observer, timestamp.to_pydatetime().replace(tzinfo=TIMEZONE)))


def load_long_frame(path: str | Path, regions: list[str]) -> pd.DataFrame:
    frame = read_csv_any(path)
    fuel_col, region_col, date_col, hour_col = frame.columns[:4]
    minute_cols = list(frame.columns[4:])

    solar = frame[
        (frame[fuel_col].astype(str).str.strip() == "태양광")
        & (frame[region_col].astype(str).str.strip().isin(regions))
    ].copy()

    long = solar.melt(
        id_vars=[fuel_col, region_col, date_col, hour_col],
        value_vars=minute_cols,
        var_name="minute_label",
        value_name="generation_wh",
    )
    long = long.rename(columns={region_col: "region", date_col: "trade_date", hour_col: "hour"})
    long["trade_date"] = pd.to_datetime(long["trade_date"])
    long["hour"] = pd.to_numeric(long["hour"], errors="coerce").astype(int)
    long["minute"] = long["minute_label"].astype(str).str.extract(r"(\d+)").astype(int)
    long["generation_wh"] = pd.to_numeric(long["generation_wh"], errors="coerce")
    long = long.dropna(subset=["generation_wh"]).copy()
    long = long[long["generation_wh"] >= 0].copy()
    long["timestamp"] = (
        long["trade_date"]
        + pd.to_timedelta(long["hour"], unit="h")
        + pd.to_timedelta(long["minute"], unit="m")
    )
    return long[["region", "timestamp", "generation_wh"]].sort_values(["region", "timestamp"]).reset_index(drop=True)


def estimate_region_capacity(hourly: pd.DataFrame, quantile: float) -> dict[str, float]:
    capacities = {}
    for region, group in hourly.groupby("region"):
        daylight = group[group["solar_elevation_mid"] > 10.0]
        source = daylight["generation_wh"] if not daylight.empty else group["generation_wh"]
        capacity = float(source.quantile(quantile))
        if capacity <= 0:
            raise ValueError(f"Estimated capacity is not positive for region: {region}")
        capacities[region] = capacity
    return capacities


def build_hourly(long: pd.DataFrame, night_threshold_wh: float, capacity_quantile: float) -> tuple[pd.DataFrame, dict]:
    hourly = (
        long.assign(hour_timestamp=long["timestamp"].dt.floor("h"))
        .groupby(["region", "hour_timestamp"], as_index=False)
        .agg(generation_wh=("generation_wh", "sum"), source_points=("generation_wh", "size"))
        .rename(columns={"hour_timestamp": "timestamp"})
        .sort_values(["region", "timestamp"])
        .reset_index(drop=True)
    )
    hourly["target_midpoint"] = hourly["timestamp"] + pd.Timedelta(minutes=30)
    hourly["solar_elevation_mid"] = hourly.apply(
        lambda row: solar_elevation(row["region"], row["target_midpoint"]),
        axis=1,
    )
    hourly["is_daylight"] = (hourly["solar_elevation_mid"] > 0).astype(int)
    hourly["physics_violation"] = (
        (hourly["solar_elevation_mid"] <= 0)
        & (hourly["generation_wh"] > night_threshold_wh)
    ).astype(int)

    clean = hourly[hourly["physics_violation"] == 0].copy()
    capacities = estimate_region_capacity(clean, capacity_quantile)
    clean["estimated_capacity_wh"] = clean["region"].map(capacities)
    clean["capacity_factor"] = (clean["generation_wh"] / clean["estimated_capacity_wh"]).clip(lower=0.0, upper=1.2)

    clean["hour"] = clean["timestamp"].dt.hour
    clean["day_of_year"] = clean["timestamp"].dt.dayofyear
    clean["hour_of_day_sin"] = np.sin(2 * np.pi * clean["hour"] / 24.0)
    clean["hour_of_day_cos"] = np.cos(2 * np.pi * clean["hour"] / 24.0)
    clean["day_of_year_sin"] = np.sin(2 * np.pi * clean["day_of_year"] / 365.25)
    clean["day_of_year_cos"] = np.cos(2 * np.pi * clean["day_of_year"] / 365.25)

    frames = []
    for region, group in clean.groupby("region"):
        group = group.sort_values("timestamp").copy()
        group["past_capacity_factor"] = group["capacity_factor"]
        group["past_capacity_factor_lag_1"] = group["capacity_factor"].shift(1)
        group["past_capacity_factor_lag_24"] = group["capacity_factor"].shift(24)
        group["rolling_mean_cf_3h"] = group["capacity_factor"].rolling(window=3, min_periods=1).mean()
        group["rolling_mean_cf_24h"] = group["capacity_factor"].rolling(window=24, min_periods=1).mean()
        group["future_capacity_factor"] = group["capacity_factor"].shift(-1)
        frames.append(group)

    dataset = pd.concat(frames, ignore_index=True)
    dataset = dataset.dropna().sort_values(["region", "timestamp"]).reset_index(drop=True)

    summary = {
        "raw_hourly_rows": int(len(hourly)),
        "clean_hourly_rows": int(len(clean)),
        "dropped_physics_violation_rows": int(hourly["physics_violation"].sum()),
        "estimated_capacity_wh_by_region": capacities,
    }
    return dataset, summary


def main() -> None:
    args = parse_args()
    regions = [region.strip() for region in args.regions.split(",") if region.strip()]
    output_root = Path(args.output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    long = load_long_frame(args.input, regions)
    dataset, summary = build_hourly(
        long,
        night_threshold_wh=args.night_threshold_wh,
        capacity_quantile=args.capacity_quantile,
    )

    val_start = pd.Timestamp(args.val_start)
    train = dataset[dataset["timestamp"] < val_start].copy()
    val = dataset[dataset["timestamp"] >= val_start].copy()

    features_path = output_root / "kpx_5min_capacity_factor_features.csv"
    train_path = output_root / "kpx_5min_capacity_factor_train.csv"
    val_path = output_root / "kpx_5min_capacity_factor_val.csv"
    manifest_path = output_root / "kpx_5min_capacity_factor_manifest.json"

    dataset.to_csv(features_path, index=False, encoding="utf-8-sig")
    train.to_csv(train_path, index=False, encoding="utf-8-sig")
    val.to_csv(val_path, index=False, encoding="utf-8-sig")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "input": str(args.input),
        "regions": regions,
        "val_start": args.val_start,
        "capacity_quantile": args.capacity_quantile,
        "night_threshold_wh": args.night_threshold_wh,
        "features_path": str(features_path),
        "train_path": str(train_path),
        "val_path": str(val_path),
        "rows_total": int(len(dataset)),
        "rows_train": int(len(train)),
        "rows_val": int(len(val)),
        "min_timestamp": dataset["timestamp"].min().isoformat() if not dataset.empty else None,
        "max_timestamp": dataset["timestamp"].max().isoformat() if not dataset.empty else None,
        "columns": list(dataset.columns),
        **summary,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
