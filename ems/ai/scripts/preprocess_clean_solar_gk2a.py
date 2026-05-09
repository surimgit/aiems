from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import xarray as xr
from astral import Observer
from astral.sun import elevation
from pyproj import Proj
from tqdm import tqdm


KST = ZoneInfo("Asia/Seoul")

DEFAULT_REGIONS = ["대전시", "울산시", "제주도", "서울시", "부산시"]

# Conservative bounding boxes for metropolitan/province-level aggregation.
# Values are min_lat, max_lat, min_lon, max_lon.
REGION_BBOX = {
    "서울시": (37.42, 37.72, 126.76, 127.20),
    "부산시": (35.00, 35.42, 128.75, 129.35),
    "대전시": (36.18, 36.52, 127.24, 127.58),
    "울산시": (35.32, 35.75, 129.00, 129.48),
    "제주도": (33.10, 33.65, 126.10, 127.05),
    "경기도": (36.85, 38.35, 126.35, 127.85),
}

REGION_CENTER = {
    "서울시": (37.5665, 126.9780),
    "부산시": (35.1796, 129.0756),
    "대전시": (36.3504, 127.3845),
    "울산시": (35.5384, 129.3114),
    "제주도": (33.4996, 126.5312),
    "경기도": (37.4138, 127.5183),
}


@dataclass(frozen=True)
class RegionMask:
    region: str
    mask: np.ndarray
    pixel_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build clean regional solar target and GK2A cloud feature tables."
    )
    parser.add_argument(
        "--data-root",
        default=r"C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data",
        help="Local s305-ai-data root.",
    )
    parser.add_argument(
        "--regions",
        default=",".join(DEFAULT_REGIONS),
        help="Comma-separated Korean region names to include.",
    )
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument(
        "--solar-elevation-clamp",
        type=float,
        default=0.0,
        help="Clamp target to zero when solar elevation is <= this value.",
    )
    parser.add_argument(
        "--max-gk2a-hours",
        type=int,
        default=None,
        help="Optional sample limit for GK2A timestamps.",
    )
    parser.add_argument(
        "--force-gk2a-parts",
        action="store_true",
        help="Rebuild monthly GK2A checkpoint parquet files even when they already exist.",
    )
    parser.add_argument("--skip-gk2a", action="store_true")
    return parser.parse_args()


def parse_stamp(path: Path) -> datetime | None:
    match = re.search(r"_(\d{12})\.nc$", path.name)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d%H%M").replace(tzinfo=KST)


def build_lat_lon_from_projection(sample_nc: Path) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(sample_nc) as ds:
        projection = ds["gk2a_imager_projection"].attrs

    width = int(projection["image_width"])
    height = int(projection["image_height"])
    pixel_size = float(projection["pixel_size"])
    upper_left_easting = float(projection["upper_left_easting"])
    upper_left_northing = float(projection["upper_left_northing"])

    x = upper_left_easting + np.arange(width) * pixel_size
    y = upper_left_northing - np.arange(height) * pixel_size
    xx, yy = np.meshgrid(x, y)

    proj = Proj(
        proj="lcc",
        lat_1=float(projection["standard_parallel1"]),
        lat_2=float(projection["standard_parallel2"]),
        lat_0=float(projection["origin_latitude"]),
        lon_0=float(projection["central_meridian"]),
        x_0=float(projection["false_easting"]),
        y_0=float(projection["false_northing"]),
        datum="WGS84",
    )
    lon, lat = proj(xx, yy, inverse=True)
    return lat, lon


def build_region_masks(lat: np.ndarray, lon: np.ndarray, regions: list[str]) -> list[RegionMask]:
    masks: list[RegionMask] = []
    for region in regions:
        if region not in REGION_BBOX:
            raise ValueError(f"No bounding box configured for region: {region}")
        min_lat, max_lat, min_lon, max_lon = REGION_BBOX[region]
        mask = (lat >= min_lat) & (lat <= max_lat) & (lon >= min_lon) & (lon <= max_lon)
        pixel_count = int(mask.sum())
        if pixel_count == 0:
            raise RuntimeError(f"Region mask has zero pixels: {region}")
        masks.append(RegionMask(region=region, mask=mask, pixel_count=pixel_count))
    return masks


def region_solar_elevation(region: str, timestamp: pd.Timestamp) -> float:
    lat, lon = REGION_CENTER[region]
    midpoint = timestamp.to_pydatetime().replace(tzinfo=KST) - pd.Timedelta(minutes=30)
    return float(elevation(Observer(latitude=lat, longitude=lon), midpoint))


def build_clean_solar_targets(data_root: Path, regions: list[str], year: int, clamp: float) -> pd.DataFrame:
    source = data_root / "processed" / "solar" / f"kpx_solar_by_region_hourly_{year}.csv"
    frame = pd.read_csv(source, parse_dates=["timestamp"])
    frame = frame[frame["region"].isin(regions)].copy()
    frame["timestamp_kst"] = frame["timestamp"]
    frame["raw_generation_kw"] = pd.to_numeric(frame["generation_kw"], errors="coerce")
    frame["solar_elevation"] = [
        region_solar_elevation(region, ts) for region, ts in zip(frame["region"], frame["timestamp_kst"])
    ]
    frame["is_daylight"] = frame["solar_elevation"] > clamp
    frame["physics_violation"] = (~frame["is_daylight"]) & (frame["raw_generation_kw"] > 0)
    frame["target_generation_kw"] = frame["raw_generation_kw"].where(frame["is_daylight"], 0.0)
    frame["night_adjusted"] = frame["physics_violation"]

    daylight = frame[frame["is_daylight"]].copy()
    capacity = (
        daylight.groupby("region")["target_generation_kw"]
        .quantile(0.995)
        .rename("estimated_capacity_kw")
        .reset_index()
    )
    frame = frame.merge(capacity, on="region", how="left")
    frame["target_capacity_factor"] = (
        frame["target_generation_kw"] / frame["estimated_capacity_kw"]
    ).clip(lower=0.0, upper=1.2)
    frame["hour"] = frame["timestamp_kst"].dt.hour
    frame["day_of_year"] = frame["timestamp_kst"].dt.dayofyear
    frame["month"] = frame["timestamp_kst"].dt.month
    frame["hour_of_day_sin"] = np.sin(2 * np.pi * frame["hour"] / 24)
    frame["hour_of_day_cos"] = np.cos(2 * np.pi * frame["hour"] / 24)
    frame["day_of_year_sin"] = np.sin(2 * np.pi * frame["day_of_year"] / 366)
    frame["day_of_year_cos"] = np.cos(2 * np.pi * frame["day_of_year"] / 366)

    return frame[
        [
            "timestamp_kst",
            "region",
            "fuel_type",
            "raw_generation_kw",
            "target_generation_kw",
            "estimated_capacity_kw",
            "target_capacity_factor",
            "solar_elevation",
            "is_daylight",
            "physics_violation",
            "night_adjusted",
            "hour",
            "day_of_year",
            "month",
            "hour_of_day_sin",
            "hour_of_day_cos",
            "day_of_year_sin",
            "day_of_year_cos",
            "source",
        ]
    ].sort_values(["timestamp_kst", "region"])


def safe_mean(values: np.ndarray) -> float:
    if values.size == 0:
        return float("nan")
    return float(np.nanmean(values))


def summarize_cla(path: Path, masks: list[RegionMask]) -> list[dict[str, object]]:
    timestamp = parse_stamp(path)
    if timestamp is None:
        return []
    rows = []
    with xr.open_dataset(path) as ds:
        ca = ds["CA"].values.astype("float32")
        cf = ds["CF"].values.astype("float32")
        ct = ds["CT"].values.astype("float32")
        ca_dqf = ds["CA_DQF"].values.astype("float32") if "CA_DQF" in ds else np.full_like(ca, np.nan)
        cf_dqf = ds["CF_DQF"].values.astype("float32") if "CF_DQF" in ds else np.full_like(cf, np.nan)
        ca = np.where((ca >= 0) & (ca <= 100), ca, np.nan)
        cf = np.where((cf >= 0) & (cf <= 10000), cf / 100.0, np.nan)
        ct = np.where((ct >= 1) & (ct <= 9), ct, np.nan)
        for item in masks:
            masked_ca = ca[item.mask]
            masked_cf = cf[item.mask]
            masked_ct = ct[item.mask]
            valid_ct = masked_ct[~np.isnan(masked_ct)]
            row: dict[str, object] = {
                "timestamp_kst": timestamp.replace(tzinfo=None),
                "region": item.region,
                "gk2a_pixel_count": item.pixel_count,
                "gk2a_ca_mean": safe_mean(masked_ca),
                "gk2a_ca_p50": float(np.nanpercentile(masked_ca, 50)),
                "gk2a_ca_p90": float(np.nanpercentile(masked_ca, 90)),
                "gk2a_cf_mean": safe_mean(masked_cf),
                "gk2a_cf_p50": float(np.nanpercentile(masked_cf, 50)),
                "gk2a_cf_p90": float(np.nanpercentile(masked_cf, 90)),
                "gk2a_ca_valid_ratio": float(np.isfinite(masked_ca).mean()),
                "gk2a_cf_valid_ratio": float(np.isfinite(masked_cf).mean()),
                "gk2a_ca_good_dqf_ratio": float((ca_dqf[item.mask] == 0).mean()),
                "gk2a_cf_good_dqf_ratio": float((cf_dqf[item.mask] == 0).mean()),
            }
            for cloud_type in range(1, 10):
                row[f"gk2a_ct_{cloud_type}_ratio"] = (
                    float((valid_ct == cloud_type).mean()) if valid_ct.size else float("nan")
                )
            rows.append(row)
    return rows


def summarize_cld(path: Path, masks: list[RegionMask]) -> list[dict[str, object]]:
    timestamp = parse_stamp(path)
    if timestamp is None:
        return []
    rows = []
    with xr.open_dataset(path) as ds:
        cld = ds["CLD"].values.astype("float32")
        cld = np.where((cld >= 0) & (cld <= 3), cld, np.nan)
        for item in masks:
            values = cld[item.mask]
            valid = values[~np.isnan(values)]
            rows.append(
                {
                    "timestamp_kst": timestamp.replace(tzinfo=None),
                    "region": item.region,
                    "gk2a_cld_valid_ratio": float(np.isfinite(values).mean()),
                    "gk2a_cld_confident_cloud_ratio": float((valid == 0).mean()) if valid.size else float("nan"),
                    "gk2a_cld_low_cloud_ratio": float((valid == 1).mean()) if valid.size else float("nan"),
                    "gk2a_cld_clear_ratio": float((valid == 2).mean()) if valid.size else float("nan"),
                    "gk2a_cld_unknown_ratio": float((valid == 3).mean()) if valid.size else float("nan"),
                }
            )
    return rows


def month_key(path: Path) -> str:
    timestamp = parse_stamp(path)
    if timestamp is None:
        return "unknown"
    return timestamp.strftime("%Y_%m")


def group_files_by_month(files: list[Path]) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in files:
        grouped[month_key(path)].append(path)
    return dict(sorted(grouped.items()))


def summarize_product_with_checkpoints(
    product: str,
    files: list[Path],
    masks: list[RegionMask],
    part_dir: Path,
    force_parts: bool,
) -> pd.DataFrame:
    summarizer = summarize_cla if product == "CLA" else summarize_cld
    frames: list[pd.DataFrame] = []
    part_dir.mkdir(parents=True, exist_ok=True)

    for key, month_files in group_files_by_month(files).items():
        part_path = part_dir / f"{product.lower()}_{key}.parquet"
        if part_path.exists() and not force_parts:
            print(f"[gk2a] load checkpoint {part_path}", flush=True)
            frames.append(pd.read_parquet(part_path))
            continue

        print(f"[gk2a] process {product} {key}: {len(month_files)} files", flush=True)
        rows: list[dict[str, object]] = []
        for path in tqdm(month_files, desc=f"{product} {key}"):
            rows.extend(summarizer(path, masks))

        frame = pd.DataFrame(rows)
        temp_path = part_path.with_suffix(".parquet.tmp")
        frame.to_parquet(temp_path, index=False)
        temp_path.replace(part_path)
        frames.append(frame)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_gk2a_features(
    data_root: Path,
    regions: list[str],
    year: int,
    max_hours: int | None,
    force_parts: bool,
) -> pd.DataFrame:
    root = data_root / "raw" / "weather" / "gk2a_le2"
    sample = next((root / "CLA" / "KO").rglob("*.nc"))
    lat, lon = build_lat_lon_from_projection(sample)
    masks = build_region_masks(lat, lon, regions)

    cla_files = sorted((root / "CLA" / "KO" / str(year)).rglob("*.nc"))
    cld_files = sorted((root / "CLD" / "KO" / str(year)).rglob("*.nc"))
    if max_hours is not None:
        cla_files = cla_files[:max_hours]
        cld_files = cld_files[:max_hours]

    part_dir = data_root / "processed" / "training" / "gk2a_cloud_clean_regions_hourly_parts"
    if max_hours is not None:
        part_dir = part_dir / f"sample_{max_hours}"

    cla_frame = summarize_product_with_checkpoints("CLA", cla_files, masks, part_dir, force_parts)
    cld_frame = summarize_product_with_checkpoints("CLD", cld_files, masks, part_dir, force_parts)
    if cla_frame.empty:
        return cld_frame
    if cld_frame.empty:
        return cla_frame
    return cla_frame.merge(cld_frame, on=["timestamp_kst", "region"], how="outer")


def write_outputs(data_root: Path, solar: pd.DataFrame, gk2a: pd.DataFrame | None, regions: list[str]) -> None:
    output_dir = data_root / "processed" / "training"
    output_dir.mkdir(parents=True, exist_ok=True)

    solar_path = output_dir / "solar_proxy_clean_regions_hourly.parquet"
    solar.to_parquet(solar_path, index=False)

    gk2a_path = None
    merged_path = None
    merged = solar
    if gk2a is not None and not gk2a.empty:
        gk2a_path = output_dir / "gk2a_cloud_clean_regions_hourly.parquet"
        gk2a.to_parquet(gk2a_path, index=False)
        merged = solar.merge(gk2a, on=["timestamp_kst", "region"], how="left")
        merged_path = output_dir / "solar_proxy_clean_regions_with_gk2a_hourly.parquet"
        merged.to_parquet(merged_path, index=False)

    manifest = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "regions": regions,
        "solar_rows": int(len(solar)),
        "gk2a_rows": int(len(gk2a)) if gk2a is not None else 0,
        "merged_rows": int(len(merged)),
        "solar_path": str(solar_path),
        "gk2a_path": str(gk2a_path) if gk2a_path else None,
        "merged_path": str(merged_path) if merged_path else None,
        "night_adjusted_rows": int(solar["night_adjusted"].sum()),
        "physics_violation_rows_by_region": solar.groupby("region")["physics_violation"].sum().astype(int).to_dict(),
        "estimated_capacity_kw_by_region": solar.groupby("region")["estimated_capacity_kw"].first().round(3).to_dict(),
        "gk2a_missing_rows_by_region": (
            merged.groupby("region")["gk2a_ca_mean"].apply(lambda s: int(s.isna().sum())).to_dict()
            if "gk2a_ca_mean" in merged
            else {}
        ),
    }
    manifest_path = output_dir / "solar_proxy_clean_regions_hourly_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root)
    regions = [region.strip() for region in args.regions.split(",") if region.strip()]
    solar = build_clean_solar_targets(data_root, regions, args.year, args.solar_elevation_clamp)
    gk2a = (
        None
        if args.skip_gk2a
        else build_gk2a_features(data_root, regions, args.year, args.max_gk2a_hours, args.force_gk2a_parts)
    )
    write_outputs(data_root, solar, gk2a, regions)


if __name__ == "__main__":
    main()
