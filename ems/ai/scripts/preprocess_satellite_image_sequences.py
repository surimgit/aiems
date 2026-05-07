from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import xarray as xr
from pyproj import Proj
from tqdm import tqdm


KST = ZoneInfo("Asia/Seoul")
MISSING_UINT8 = np.uint8(255)
CHANNEL_NAMES = np.array(["CA", "CF", "CT", "CLD"])

DEFAULT_REGIONS = ["대전시", "울산시", "제주도", "서울시", "부산시"]

REGION_BBOX = {
    "서울시": (37.42, 37.72, 126.76, 127.20),
    "부산시": (35.00, 35.42, 128.75, 129.35),
    "대전시": (36.18, 36.52, 127.24, 127.58),
    "울산시": (35.32, 35.75, 129.00, 129.48),
    "제주도": (33.10, 33.65, 126.10, 127.05),
    "경기도": (36.85, 38.35, 126.35, 127.85),
}

REGION_SLUG = {
    "서울시": "seoul",
    "부산시": "busan",
    "대전시": "daejeon",
    "울산시": "ulsan",
    "제주도": "jeju",
    "경기도": "gyeonggi",
}


@dataclass(frozen=True)
class RegionWindow:
    region: str
    slug: str
    y0: int
    y1: int
    x0: int
    x1: int
    pixel_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build GK2A image sequence shards for CNN/near-term solar prediction."
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
    parser.add_argument("--image-size", type=int, default=96)
    parser.add_argument(
        "--context-pixels",
        type=int,
        default=64,
        help="Extra GK2A source pixels around each regional bounding box to capture incoming cloud movement.",
    )
    parser.add_argument("--sequence-length", type=int, default=3)
    parser.add_argument(
        "--horizons",
        default="1,2,3,6",
        help="Comma-separated future target horizons in hours.",
    )
    parser.add_argument(
        "--allow-missing-frames",
        action="store_true",
        help="Keep sequences with missing CLA/CLD frames and encode missing channels as 255.",
    )
    parser.add_argument(
        "--max-anchors",
        type=int,
        default=None,
        help="Optional sample limit for anchor timestamps.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild monthly shards even when checkpoint files already exist.",
    )
    return parser.parse_args()


def parse_stamp(path: Path) -> pd.Timestamp | None:
    match = re.search(r"_(\d{12})\.nc$", path.name)
    if not match:
        return None
    return pd.Timestamp(datetime.strptime(match.group(1), "%Y%m%d%H%M"))


def stamp(timestamp: pd.Timestamp) -> str:
    return pd.Timestamp(timestamp).strftime("%Y%m%d%H%M")


def sequence_id(timestamp: pd.Timestamp, region: str) -> str:
    return f"{stamp(timestamp)}__{REGION_SLUG[region]}"


def build_file_index(root: Path, product: str, year: int) -> dict[pd.Timestamp, Path]:
    files = sorted((root / product / "KO" / str(year)).rglob("*.nc"))
    index: dict[pd.Timestamp, Path] = {}
    for path in files:
        timestamp = parse_stamp(path)
        if timestamp is not None:
            index[timestamp] = path
    return index


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


def build_region_windows(lat: np.ndarray, lon: np.ndarray, regions: list[str], context_pixels: int) -> list[RegionWindow]:
    windows: list[RegionWindow] = []
    height, width = lat.shape
    for region in regions:
        min_lat, max_lat, min_lon, max_lon = REGION_BBOX[region]
        mask = (lat >= min_lat) & (lat <= max_lat) & (lon >= min_lon) & (lon <= max_lon)
        yy, xx = np.where(mask)
        if yy.size == 0:
            raise RuntimeError(f"Region window has zero pixels: {region}")
        y0 = max(int(yy.min()) - context_pixels, 0)
        y1 = min(int(yy.max()) + 1 + context_pixels, height)
        x0 = max(int(xx.min()) - context_pixels, 0)
        x1 = min(int(xx.max()) + 1 + context_pixels, width)
        windows.append(
            RegionWindow(
                region=region,
                slug=REGION_SLUG[region],
                y0=y0,
                y1=y1,
                x0=x0,
                x1=x1,
                pixel_count=int(mask.sum()),
            )
        )
    return windows


def resize_nearest(array: np.ndarray, image_size: int) -> np.ndarray:
    y_idx = np.linspace(0, array.shape[-2] - 1, image_size).round().astype(np.int64)
    x_idx = np.linspace(0, array.shape[-1] - 1, image_size).round().astype(np.int64)
    return array[..., y_idx, :][..., :, x_idx]


def to_uint8_channel(values: np.ndarray, valid_min: float, valid_max: float, scale: float = 1.0) -> np.ndarray:
    scaled = values.astype("float32") * scale
    valid = np.isfinite(scaled) & (scaled >= valid_min) & (scaled <= valid_max)
    encoded = np.full(scaled.shape, MISSING_UINT8, dtype="uint8")
    encoded[valid] = np.rint(scaled[valid]).clip(0, 254).astype("uint8")
    return encoded


def load_cla(path: Path | None) -> tuple[np.ndarray, bool]:
    if path is None:
        return np.full((3, 900, 900), MISSING_UINT8, dtype="uint8"), False
    with xr.open_dataset(path) as ds:
        ca = to_uint8_channel(ds["CA"].values, 0, 100)
        cf = to_uint8_channel(ds["CF"].values, 0, 10000, scale=0.01)
        ct = to_uint8_channel(ds["CT"].values, 1, 9)
    return np.stack([ca, cf, ct], axis=0), True


def load_cld(path: Path | None) -> tuple[np.ndarray, bool]:
    if path is None:
        return np.full((1, 900, 900), MISSING_UINT8, dtype="uint8"), False
    with xr.open_dataset(path) as ds:
        cld = to_uint8_channel(ds["CLD"].values, 0, 3)
    return cld[np.newaxis, ...], True


def month_key(timestamp: pd.Timestamp) -> str:
    return pd.Timestamp(timestamp).strftime("%Y_%m")


def load_targets(data_root: Path) -> pd.DataFrame:
    path = data_root / "processed" / "training" / "solar_proxy_clean_regions_hourly.parquet"
    frame = pd.read_parquet(path)
    frame["timestamp_kst"] = pd.to_datetime(frame["timestamp_kst"])
    return frame


def target_lookup(targets: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], dict[str, object]]:
    rows: dict[tuple[str, pd.Timestamp], dict[str, object]] = {}
    for item in targets.to_dict("records"):
        rows[(str(item["region"]), pd.Timestamp(item["timestamp_kst"]))] = item
    return rows


def complete_sequence_available(
    anchor: pd.Timestamp,
    sequence_length: int,
    cla_index: dict[pd.Timestamp, Path],
    cld_index: dict[pd.Timestamp, Path],
) -> bool:
    for offset in reversed(range(sequence_length)):
        timestamp = anchor - pd.Timedelta(hours=offset)
        if timestamp not in cla_index or timestamp not in cld_index:
            return False
    return True


def build_month_shard(
    month: str,
    anchors: list[pd.Timestamp],
    windows: list[RegionWindow],
    lookup: dict[tuple[str, pd.Timestamp], dict[str, object]],
    cla_index: dict[pd.Timestamp, Path],
    cld_index: dict[pd.Timestamp, Path],
    image_size: int,
    sequence_length: int,
    horizons: list[int],
    allow_missing_frames: bool,
    output_dir: Path,
) -> dict[str, object]:
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    image_path = images_dir / f"images_{month}.npz"
    sequence_path = metadata_dir / f"sequences_{month}.parquet"
    sample_path = metadata_dir / f"samples_{month}.parquet"

    image_rows: list[np.ndarray] = []
    frame_available_rows: list[np.ndarray] = []
    sequence_rows: list[dict[str, object]] = []
    sample_rows: list[dict[str, object]] = []

    @lru_cache(maxsize=16)
    def load_frame(timestamp_text: str) -> tuple[np.ndarray, np.ndarray]:
        timestamp = pd.Timestamp(timestamp_text)
        cla, cla_available = load_cla(cla_index.get(timestamp))
        cld, cld_available = load_cld(cld_index.get(timestamp))
        frame = np.concatenate([cla, cld], axis=0)
        available = np.array([cla_available, cld_available], dtype="uint8")
        return frame, available

    for anchor in tqdm(anchors, desc=f"satellite {month}"):
        if not allow_missing_frames and not complete_sequence_available(anchor, sequence_length, cla_index, cld_index):
            continue

        full_frames: list[np.ndarray] = []
        frame_available: list[np.ndarray] = []
        source_timestamps: list[str] = []
        for offset in reversed(range(sequence_length)):
            source_timestamp = anchor - pd.Timedelta(hours=offset)
            frame, available = load_frame(stamp(source_timestamp))
            full_frames.append(frame)
            frame_available.append(available)
            source_timestamps.append(stamp(source_timestamp))

        stacked_full = np.stack(full_frames, axis=0)
        available_stacked = np.stack(frame_available, axis=0)

        for window in windows:
            sid = sequence_id(anchor, window.region)
            crop = stacked_full[:, :, window.y0 : window.y1, window.x0 : window.x1]
            resized = resize_nearest(crop, image_size).astype("uint8", copy=False)
            sequence_index = len(image_rows)
            image_rows.append(resized)
            frame_available_rows.append(available_stacked)

            sequence_rows.append(
                {
                    "sequence_index": sequence_index,
                    "sequence_id": sid,
                    "anchor_timestamp_kst": anchor,
                    "region": window.region,
                    "region_slug": window.slug,
                    "source_timestamps": ",".join(source_timestamps),
                    "image_path": str(image_path),
                    "image_shape": f"{sequence_length},4,{image_size},{image_size}",
                    "source_window_y0": window.y0,
                    "source_window_y1": window.y1,
                    "source_window_x0": window.x0,
                    "source_window_x1": window.x1,
                    "source_pixel_count": window.pixel_count,
                    "all_frames_available": bool(available_stacked.all()),
                }
            )

            for horizon in horizons:
                target_timestamp = anchor + pd.Timedelta(hours=horizon)
                target = lookup.get((window.region, target_timestamp))
                if target is None:
                    continue
                sample_rows.append(
                    {
                        "sequence_index": sequence_index,
                        "sequence_id": sid,
                        "anchor_timestamp_kst": anchor,
                        "target_timestamp_kst": target_timestamp,
                        "region": window.region,
                        "region_slug": window.slug,
                        "horizon_hours": horizon,
                        "target_capacity_factor": target["target_capacity_factor"],
                        "target_generation_kw": target["target_generation_kw"],
                        "raw_generation_kw": target["raw_generation_kw"],
                        "estimated_capacity_kw": target["estimated_capacity_kw"],
                        "solar_elevation": target["solar_elevation"],
                        "is_daylight": target["is_daylight"],
                        "physics_violation": target["physics_violation"],
                        "night_adjusted": target["night_adjusted"],
                        "hour": target["hour"],
                        "day_of_year": target["day_of_year"],
                        "month": target["month"],
                        "hour_of_day_sin": target["hour_of_day_sin"],
                        "hour_of_day_cos": target["hour_of_day_cos"],
                        "day_of_year_sin": target["day_of_year_sin"],
                        "day_of_year_cos": target["day_of_year_cos"],
                    }
                )

    if image_rows:
        images = np.stack(image_rows, axis=0)
        frame_available_array = np.stack(frame_available_rows, axis=0)
    else:
        images = np.empty((0, sequence_length, 4, image_size, image_size), dtype="uint8")
        frame_available_array = np.empty((0, sequence_length, 2), dtype="uint8")

    temp_image_path = image_path.with_suffix(".npz.tmp")
    with temp_image_path.open("wb") as file:
        np.savez_compressed(
            file,
            images=images,
            frame_available=frame_available_array,
            channel_names=CHANNEL_NAMES,
            missing_value=np.array([MISSING_UINT8], dtype="uint8"),
        )
    temp_image_path.replace(image_path)

    sequences = pd.DataFrame(sequence_rows)
    samples = pd.DataFrame(sample_rows)
    sequences.to_parquet(sequence_path, index=False)
    samples.to_parquet(sample_path, index=False)

    return {
        "month": month,
        "anchors_input": len(anchors),
        "sequences": int(len(sequences)),
        "samples": int(len(samples)),
        "image_path": str(image_path),
        "sequence_path": str(sequence_path),
        "sample_path": str(sample_path),
        "image_size_bytes": int(image_path.stat().st_size),
    }


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root)
    regions = [region.strip() for region in args.regions.split(",") if region.strip()]
    horizons = [int(item.strip()) for item in args.horizons.split(",") if item.strip()]

    gk2a_root = data_root / "raw" / "weather" / "gk2a_le2"
    cla_index = build_file_index(gk2a_root, "CLA", args.year)
    cld_index = build_file_index(gk2a_root, "CLD", args.year)
    sample_nc = next((gk2a_root / "CLA" / "KO" / str(args.year)).rglob("*.nc"))
    lat, lon = build_lat_lon_from_projection(sample_nc)
    windows = build_region_windows(lat, lon, regions, args.context_pixels)

    targets = load_targets(data_root)
    targets = targets[(targets["timestamp_kst"].dt.year == args.year) & (targets["region"].isin(regions))]
    lookup = target_lookup(targets)

    anchors = sorted(targets["timestamp_kst"].drop_duplicates().tolist())
    if args.max_anchors is not None:
        anchors = anchors[: args.max_anchors]

    grouped: dict[str, list[pd.Timestamp]] = {}
    for anchor in anchors:
        grouped.setdefault(month_key(anchor), []).append(pd.Timestamp(anchor))

    output_dir = data_root / "processed" / "training" / "satellite_image_clean_regions"
    output_dir.mkdir(parents=True, exist_ok=True)

    month_results: list[dict[str, object]] = []
    for month, month_anchors in grouped.items():
        image_path = output_dir / "images" / f"images_{month}.npz"
        sequence_path = output_dir / "metadata" / f"sequences_{month}.parquet"
        sample_path = output_dir / "metadata" / f"samples_{month}.parquet"
        if image_path.exists() and sequence_path.exists() and sample_path.exists() and not args.force:
            sequences = pd.read_parquet(sequence_path)
            samples = pd.read_parquet(sample_path)
            result = {
                "month": month,
                "anchors_input": len(month_anchors),
                "sequences": int(len(sequences)),
                "samples": int(len(samples)),
                "image_path": str(image_path),
                "sequence_path": str(sequence_path),
                "sample_path": str(sample_path),
                "image_size_bytes": int(image_path.stat().st_size),
                "loaded_checkpoint": True,
            }
            print(f"[satellite] load checkpoint {month}", flush=True)
        else:
            result = build_month_shard(
                month=month,
                anchors=month_anchors,
                windows=windows,
                lookup=lookup,
                cla_index=cla_index,
                cld_index=cld_index,
                image_size=args.image_size,
                sequence_length=args.sequence_length,
                horizons=horizons,
                allow_missing_frames=args.allow_missing_frames,
                output_dir=output_dir,
            )
            result["loaded_checkpoint"] = False
        month_results.append(result)

    sequence_frames = [
        pd.read_parquet(output_dir / "metadata" / f"sequences_{item['month']}.parquet") for item in month_results
    ]
    sample_frames = [
        pd.read_parquet(output_dir / "metadata" / f"samples_{item['month']}.parquet") for item in month_results
    ]
    sequences_all = pd.concat(sequence_frames, ignore_index=True) if sequence_frames else pd.DataFrame()
    samples_all = pd.concat(sample_frames, ignore_index=True) if sample_frames else pd.DataFrame()
    sequences_all.to_parquet(output_dir / "metadata" / "sequences_all.parquet", index=False)
    samples_all.to_parquet(output_dir / "metadata" / "samples_all.parquet", index=False)

    manifest = {
        "generated_at": datetime.now(KST).isoformat(timespec="seconds"),
        "data_root": str(data_root),
        "regions": regions,
        "year": args.year,
        "image_size": args.image_size,
        "context_pixels": args.context_pixels,
        "sequence_length": args.sequence_length,
        "channels": CHANNEL_NAMES.tolist(),
        "channel_encoding": {
            "CA": "cloud amount 0..100, missing=255",
            "CF": "cloud fraction percent 0..100, missing=255",
            "CT": "cloud type 1..9, missing=255",
            "CLD": "scene analysis 0..3, missing=255",
        },
        "horizons": horizons,
        "allow_missing_frames": bool(args.allow_missing_frames),
        "month_results": month_results,
        "total_sequences": int(len(sequences_all)),
        "total_samples": int(len(samples_all)),
        "metadata_dir": str(output_dir / "metadata"),
        "images_dir": str(output_dir / "images"),
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
