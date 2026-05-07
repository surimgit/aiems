"""Build satellite training bundle with wind-aligned cloud and visibility features.

This is the v7 experiment bundle. It starts from the v4 satellite anomaly
comparison bundle, then adds:

- safe ASOS wind/weather features from stable leading numeric columns
- ASOS visibility / low-visibility flags from correctly aligned raw ASOS text
- wind-aligned upstream cloud statistics from the current satellite patch

The AirKorea PM feature is intentionally excluded because the available API only
returns recent 3-month measurements, not the 2025 full-year archive.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BASE_BUNDLE = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\server_upload"
    r"\satellite_image_anomaly_compare_regions_2025_20260506_171847"
)
DEFAULT_ASOS_RAW_ROOT = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data\raw\weather\kma_asos_apihub"
)
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\SSAFY\Project_Minsu\S305\server_upload")

VARIANTS = ("no_filter", "mild_filter", "strong_filter")
SOURCE_PIXEL_KM = 2.0
IMAGE_SIZE = 64
UPWIND_WINDOW_RADIUS = 8
MAX_UPWIND_DISTANCE_KM = 180.0
MISSING_UINT8 = 255

KMA_ASOS_COLUMNS = [
    "TM",
    "STN",
    "WD",
    "WS",
    "GST_WD",
    "GST_WS",
    "GST_TM",
    "PA",
    "PS",
    "PT",
    "PR",
    "TA",
    "TD",
    "HM",
    "PV",
    "RN",
    "RN_DAY",
    "RN_JUN",
    "RN_INT",
    "SD_HR3",
    "SD_DAY",
    "SD_TOT",
    "WC",
    "WP",
    "WW",
    "CA_TOT",
    "CA_MID",
    "CH_MIN",
    "CT",
    "CT_TOP",
    "CT_MID",
    "CT_LOW",
    "VS",
    "SS",
    "SI",
    "ST_GD",
    "TS",
    "TE_005",
    "TE_01",
    "TE_02",
    "TE_03",
    "ST_SEA",
    "WH",
    "BF",
    "IR",
    "IX",
]

REGION_STATIONS = [
    {"region": "서울시", "region_slug": "seoul", "station_id": 108, "station_name": "서울"},
    {"region": "부산시", "region_slug": "busan", "station_id": 159, "station_name": "부산"},
    {"region": "대전시", "region_slug": "daejeon", "station_id": 133, "station_name": "대전"},
    {"region": "울산시", "region_slug": "ulsan", "station_id": 152, "station_name": "울산"},
    {"region": "제주도", "region_slug": "jeju", "station_id": 184, "station_name": "제주"},
]

FOG_OR_MIST_WW_CODES = {10, 11, 12, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49}
HAZE_WW_CODES = {5, 6, 7, 8, 9}

SAFE_MODEL_FEATURE_COLS = [
    "wind_u",
    "wind_v",
    "wind_speed_ms",
    "wind_dir_deg",
    "wind_dir_sin",
    "wind_dir_cos",
    "asos_ta",
    "asos_hm",
    "asos_rn",
    "asos_vs",
    "asos_low_visibility_flag",
    "asos_very_low_visibility_flag",
    "asos_fog_or_mist_flag",
    "asos_haze_code_flag",
]

UPWIND_FEATURE_COLS = [
    "upwind_distance_scaled",
    "upwind_edge_clipped",
    "upwind_ca_scaled",
    "upwind_cf_scaled",
    "upwind_cld_scaled",
    "upwind_cld_ge2_frac",
    "upwind_missing_frac",
    "upwind_center_cf_diff",
    "upwind_center_cld_diff",
]


@dataclass(frozen=True)
class LoadedImages:
    name: str
    images: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-bundle", type=Path, default=DEFAULT_BASE_BUNDLE)
    parser.add_argument("--asos-raw-root", type=Path, default=DEFAULT_ASOS_RAW_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--name", default="satellite_image_upwind_visibility_regions_2025")
    return parser.parse_args()


def copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def parse_asos_text(raw_text: str) -> pd.DataFrame:
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)

    if not lines:
        return pd.DataFrame(columns=KMA_ASOS_COLUMNS)

    frame = pd.read_csv(
        StringIO("\n".join(lines)),
        sep=r"\s+",
        engine="python",
        header=None,
        names=KMA_ASOS_COLUMNS,
    )
    return frame


def clean_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if column in {"TM", "CT"}:
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce")
        out.loc[out[column] <= -900, column] = np.nan
    return out


def load_asos_from_raw(raw_root: Path, year: int = 2025) -> pd.DataFrame:
    frames = []
    for station in REGION_STATIONS:
        raw_dir = (
            raw_root
            / station["region_slug"]
            / f"station_{station['station_id']}"
            / "hourly_raw"
        )
        if not raw_dir.exists():
            raise FileNotFoundError(raw_dir)

        station_frames = []
        for month in range(1, 13):
            raw_path = raw_dir / f"{year:04d}-{month:02d}.txt"
            if not raw_path.exists():
                raise FileNotFoundError(raw_path)
            parsed = parse_asos_text(raw_path.read_text(encoding="utf-8"))
            station_frames.append(parsed)

        frame = pd.concat(station_frames, ignore_index=True)
        frame = clean_numeric(frame)
        frame["timestamp_kst"] = pd.to_datetime(frame["TM"].astype(str), format="%Y%m%d%H%M", errors="coerce")
        frame["region"] = station["region"]
        frame["region_slug"] = station["region_slug"]
        frame["station_id"] = int(station["station_id"])
        frame["station_name"] = station["station_name"]
        frames.append(frame)

    all_frame = pd.concat(frames, ignore_index=True)
    all_frame = all_frame.sort_values(["region", "timestamp_kst"]).reset_index(drop=True)
    return all_frame


def build_asos_features(raw_root: Path) -> pd.DataFrame:
    asos = load_asos_from_raw(raw_root)
    out = asos[
        [
            "timestamp_kst",
            "region",
            "region_slug",
            "station_id",
            "station_name",
            "WD",
            "WS",
            "TA",
            "HM",
            "RN",
            "WW",
            "VS",
        ]
    ].copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["timestamp_kst"])
    out = out.rename(
        columns={
            "station_id": "asos_station_id",
            "station_name": "asos_station_name",
            "WD": "asos_wd_code",
            "WS": "wind_speed_ms",
            "TA": "asos_ta",
            "HM": "asos_hm",
            "RN": "asos_rn",
            "WW": "asos_ww_code",
            "VS": "asos_vs",
        }
    )

    numeric_cols = ["asos_wd_code", "wind_speed_ms", "asos_ta", "asos_hm", "asos_rn", "asos_ww_code", "asos_vs"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        out.loc[out[col] <= -900, col] = np.nan

    out.loc[out["asos_wd_code"] < 0, "asos_wd_code"] = np.nan
    out.loc[out["wind_speed_ms"] < 0, "wind_speed_ms"] = np.nan
    out.loc[out["asos_hm"] < 0, "asos_hm"] = np.nan
    out.loc[out["asos_rn"] < 0, "asos_rn"] = 0.0
    out.loc[out["asos_vs"] < 0, "asos_vs"] = np.nan

    valid_wind = (
        out["asos_wd_code"].notna()
        & out["wind_speed_ms"].notna()
        & (out["asos_wd_code"] > 0)
        & (out["wind_speed_ms"] > 0)
    )
    wind_dir_deg = np.mod(out["asos_wd_code"].astype(float) * 10.0, 360.0)
    radians = np.deg2rad(wind_dir_deg)
    out["wind_dir_deg"] = wind_dir_deg.where(valid_wind, 0.0).astype("float32")
    out["wind_dir_sin"] = np.sin(radians).where(valid_wind, 0.0).astype("float32")
    out["wind_dir_cos"] = np.cos(radians).where(valid_wind, 0.0).astype("float32")
    out["wind_u"] = (out["wind_speed_ms"] * out["wind_dir_sin"]).where(valid_wind, 0.0).astype("float32")
    out["wind_v"] = (out["wind_speed_ms"] * out["wind_dir_cos"]).where(valid_wind, 0.0).astype("float32")

    ww = out["asos_ww_code"].fillna(-1).astype(int)
    vs = out["asos_vs"]
    out["asos_low_visibility_flag"] = ((vs > 0) & (vs <= 3000)).astype("float32")
    out["asos_very_low_visibility_flag"] = ((vs > 0) & (vs <= 1000)).astype("float32")
    out["asos_fog_or_mist_flag"] = (ww.isin(FOG_OR_MIST_WW_CODES) | ((vs > 0) & (vs <= 1000))).astype("float32")
    out["asos_haze_code_flag"] = ww.isin(HAZE_WW_CODES).astype("float32")
    return out


def add_asos_features(frame: pd.DataFrame, asos: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])

    keep_cols = [
        "target_timestamp_kst",
        "region",
        "asos_station_id",
        "asos_station_name",
        "asos_wd_code",
        "wind_speed_ms",
        "asos_ta",
        "asos_hm",
        "asos_rn",
        "asos_ww_code",
        "asos_vs",
        "wind_dir_deg",
        "wind_dir_sin",
        "wind_dir_cos",
        "wind_u",
        "wind_v",
        "asos_low_visibility_flag",
        "asos_very_low_visibility_flag",
        "asos_fog_or_mist_flag",
        "asos_haze_code_flag",
    ]
    merged = out.merge(
        asos[keep_cols],
        on=["target_timestamp_kst", "region"],
        how="left",
        validate="many_to_one",
    )

    feature_cols = SAFE_MODEL_FEATURE_COLS
    merged["asos_missing"] = merged["wind_speed_ms"].isna()
    merged["asos_any_missing"] = merged[feature_cols].isna().any(axis=1)

    for col in feature_cols:
        missing_col = f"{col}_missing"
        merged[missing_col] = merged[col].isna()
        median = merged[col].median(skipna=True)
        fill_value = 0.0 if pd.isna(median) else float(median)
        merged[col] = merged[col].fillna(fill_value).astype("float32")

    merged["wind_u_scaled"] = (merged["wind_u"] / 15.0).astype("float32")
    merged["wind_v_scaled"] = (merged["wind_v"] / 15.0).astype("float32")
    merged["wind_speed_scaled"] = (merged["wind_speed_ms"] / 15.0).astype("float32")
    merged["asos_ta_scaled"] = ((merged["asos_ta"] + 30.0) / 70.0).astype("float32")
    merged["asos_hm_scaled"] = (merged["asos_hm"] / 100.0).astype("float32")
    merged["asos_rn_log1p"] = np.log1p(np.clip(merged["asos_rn"].to_numpy(dtype=float), 0, None)).astype("float32")
    merged["asos_vs_scaled"] = (np.clip(merged["asos_vs"].to_numpy(dtype=float), 0, 5000) / 5000.0).astype("float32")
    return merged


def safe_mean(values: np.ndarray) -> tuple[float, float]:
    valid = values != MISSING_UINT8
    if not valid.any():
        return 0.0, 1.0
    return float(values[valid].mean()), float(1.0 - valid.mean())


def window_slice(center: float, size: int, radius: int) -> slice:
    rounded = int(round(center))
    start = max(rounded - radius, 0)
    stop = min(rounded + radius + 1, size)
    return slice(start, stop)


def add_upwind_features(frame: pd.DataFrame, images_dir: Path, sequences: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    seq_cols = [
        "sequence_index",
        "sequence_id",
        "source_window_y0",
        "source_window_y1",
        "source_window_x0",
        "source_window_x1",
    ]
    if "source_window_y0" not in out.columns:
        out = out.merge(sequences[seq_cols], on=["sequence_index", "sequence_id"], how="left", validate="many_to_one")

    feature_values = {col: np.zeros(len(out), dtype="float32") for col in UPWIND_FEATURE_COLS}
    image_file = out["image_file"].map(lambda value: Path(str(value)).name).to_numpy()
    image_row = out["image_row"].astype("int64").to_numpy()
    horizon = out["horizon_hours"].astype("float32").to_numpy()
    wind_speed = out["wind_speed_ms"].astype("float32").to_numpy()
    wind_dir = out["wind_dir_deg"].astype("float32").to_numpy()
    source_width = (out["source_window_x1"].astype("float32") - out["source_window_x0"].astype("float32")).to_numpy()
    source_height = (out["source_window_y1"].astype("float32") - out["source_window_y0"].astype("float32")).to_numpy()

    center = (IMAGE_SIZE - 1) / 2.0
    center_slice = window_slice(center, IMAGE_SIZE, UPWIND_WINDOW_RADIUS)

    loaded: dict[str, LoadedImages] = {}
    for idx in range(len(out)):
        name = str(image_file[idx])
        item = loaded.get(name)
        if item is None:
            path = images_dir / name
            item = LoadedImages(name=name, images=np.load(path)["images"])
            loaded[name] = item

        image = item.images[int(image_row[idx]), -1]
        km_per_px_x = max(float(source_width[idx]) * SOURCE_PIXEL_KM / IMAGE_SIZE, 1e-6)
        km_per_px_y = max(float(source_height[idx]) * SOURCE_PIXEL_KM / IMAGE_SIZE, 1e-6)
        distance_km = float(max(wind_speed[idx], 0.0) * max(horizon[idx], 0.0) * 3.6)
        capped_distance_km = min(distance_km, MAX_UPWIND_DISTANCE_KM)
        radians = math.radians(float(wind_dir[idx]))

        x = center + math.sin(radians) * capped_distance_km / km_per_px_x
        y = center - math.cos(radians) * capped_distance_km / km_per_px_y
        clipped_x = float(np.clip(x, 0, IMAGE_SIZE - 1))
        clipped_y = float(np.clip(y, 0, IMAGE_SIZE - 1))
        edge_clipped = float((abs(clipped_x - x) > 1e-6) or (abs(clipped_y - y) > 1e-6))

        ys = window_slice(clipped_y, IMAGE_SIZE, UPWIND_WINDOW_RADIUS)
        xs = window_slice(clipped_x, IMAGE_SIZE, UPWIND_WINDOW_RADIUS)
        center_ys = center_slice
        center_xs = center_slice

        ca, missing_ca = safe_mean(image[0, ys, xs])
        cf, missing_cf = safe_mean(image[1, ys, xs])
        cld, missing_cld = safe_mean(image[3, ys, xs])
        center_cf, _ = safe_mean(image[1, center_ys, center_xs])
        center_cld, _ = safe_mean(image[3, center_ys, center_xs])

        cld_window = image[3, ys, xs]
        valid_cld = cld_window != MISSING_UINT8
        if valid_cld.any():
            cld_ge2 = float((cld_window[valid_cld] >= 2).mean())
        else:
            cld_ge2 = 0.0

        feature_values["upwind_distance_scaled"][idx] = capped_distance_km / MAX_UPWIND_DISTANCE_KM
        feature_values["upwind_edge_clipped"][idx] = edge_clipped
        # The current image bundle stores CA/CF as 0/1 cloud masks, not 0..100.
        feature_values["upwind_ca_scaled"][idx] = ca
        feature_values["upwind_cf_scaled"][idx] = cf
        feature_values["upwind_cld_scaled"][idx] = cld / 3.0
        feature_values["upwind_cld_ge2_frac"][idx] = cld_ge2
        feature_values["upwind_missing_frac"][idx] = max(missing_ca, missing_cf, missing_cld)
        feature_values["upwind_center_cf_diff"][idx] = cf - center_cf
        feature_values["upwind_center_cld_diff"][idx] = (cld - center_cld) / 3.0

    for col, values in feature_values.items():
        out[col] = values
    return out


def add_v7_features(frame: pd.DataFrame, asos: pd.DataFrame, images_dir: Path, sequences: pd.DataFrame) -> pd.DataFrame:
    with_asos = add_asos_features(frame, asos)
    return add_upwind_features(with_asos, images_dir, sequences)


def write_variant_files(metadata_dir: Path, name: str, all_frame: pd.DataFrame) -> dict[str, int]:
    all_path = metadata_dir / f"samples_daylight_{name}_all.parquet"
    train_path = metadata_dir / f"samples_daylight_{name}_train.parquet"
    val_path = metadata_dir / f"samples_daylight_{name}_val.parquet"

    all_frame.to_parquet(all_path, index=False)
    train = all_frame[all_frame["split"] == "train"].copy()
    val = all_frame[all_frame["split"] == "val"].copy()
    train.to_parquet(train_path, index=False)
    val.to_parquet(val_path, index=False)

    horizon_dir = metadata_dir / "horizon" / name
    if horizon_dir.exists():
        shutil.rmtree(horizon_dir)
    horizon_dir.mkdir(parents=True, exist_ok=True)

    for horizon in sorted(all_frame["horizon_hours"].astype(int).unique()):
        subset = all_frame[all_frame["horizon_hours"].astype(int) == horizon].copy()
        subset[subset["split"] == "train"].to_parquet(horizon_dir / f"samples_h{horizon}_train.parquet", index=False)
        subset[subset["split"] == "val"].to_parquet(horizon_dir / f"samples_h{horizon}_val.parquet", index=False)

    return {
        "all": int(len(all_frame)),
        "train": int(len(train)),
        "val": int(len(val)),
        "asos_missing_rows": int(all_frame["asos_missing"].sum()),
        "asos_any_missing_rows": int(all_frame["asos_any_missing"].sum()),
        "low_visibility_rows": int(all_frame["asos_low_visibility_flag"].sum()),
        "very_low_visibility_rows": int(all_frame["asos_very_low_visibility_flag"].sum()),
        "fog_or_mist_rows": int(all_frame["asos_fog_or_mist_flag"].sum()),
        "upwind_edge_clipped_rows": int(all_frame["upwind_edge_clipped"].sum()),
    }


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in sorted(src_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(src_dir.parent))


def write_readme(path: Path) -> None:
    path.write_text(
        """# Satellite Upwind + Visibility Bundle v7

This bundle adds explicit wind-aligned upstream cloud features and ASOS
visibility / low-visibility flags on top of the v6 safe wind features.

Important metadata files:

- `metadata/samples_modeling_all_upwind_visibility_v7.parquet`
- `metadata/samples_daylight_no_filter_train/val.parquet`
- `metadata/samples_daylight_mild_filter_train/val.parquet`
- `metadata/samples_daylight_strong_filter_train/val.parquet`

Additional scaled feature columns:

- `asos_vs_scaled`
- `asos_low_visibility_flag`
- `asos_very_low_visibility_flag`
- `asos_fog_or_mist_flag`
- `asos_haze_code_flag`
- `upwind_distance_scaled`
- `upwind_edge_clipped`
- `upwind_ca_scaled`
- `upwind_cf_scaled`
- `upwind_cld_scaled`
- `upwind_cld_ge2_frac`
- `upwind_missing_frac`
- `upwind_center_cf_diff`
- `upwind_center_cld_diff`

AirKorea PM10/PM2.5 is excluded from this bundle because the available API
returns recent 3-month measurements only, not a 2025 full-year archive.
""",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    base = args.base_bundle.resolve()
    output_root = args.output_root.resolve()
    raw_root = args.asos_raw_root.resolve()

    for required in [base / "images", base / "metadata" / "samples_modeling_all_v4.parquet", base / "metadata" / "sequences_all.parquet"]:
        if not required.exists():
            raise FileNotFoundError(required)

    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_dir = output_root / f"{args.name}_{timestamp}"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)

    copy_dir(base / "images", bundle_dir / "images")
    copy_dir(base / "metadata", bundle_dir / "metadata")
    if (base / "manifest.json").exists():
        shutil.copy2(base / "manifest.json", bundle_dir / "manifest.json")

    metadata_dir = bundle_dir / "metadata"
    images_dir = bundle_dir / "images"
    sequences = pd.read_parquet(base / "metadata" / "sequences_all.parquet")
    asos = build_asos_features(raw_root)
    asos.to_parquet(metadata_dir / "asos_hourly_features_visibility_v7.parquet", index=False)

    all_v4 = pd.read_parquet(base / "metadata" / "samples_modeling_all_v4.parquet")
    all_v7 = add_v7_features(all_v4, asos, images_dir, sequences)
    all_v7.to_parquet(metadata_dir / "samples_modeling_all_upwind_visibility_v7.parquet", index=False)

    variant_counts: dict[str, dict[str, int]] = {}
    for variant in VARIANTS:
        path = base / "metadata" / f"samples_daylight_{variant}_all.parquet"
        frame = pd.read_parquet(path)
        frame_v7 = add_v7_features(frame, asos, images_dir, sequences)
        variant_counts[variant] = write_variant_files(metadata_dir, variant, frame_v7)

    feature_columns = [
        "wind_u_scaled",
        "wind_v_scaled",
        "wind_speed_scaled",
        "wind_dir_sin",
        "wind_dir_cos",
        "asos_ta_scaled",
        "asos_hm_scaled",
        "asos_rn_log1p",
        "asos_vs_scaled",
        "asos_low_visibility_flag",
        "asos_very_low_visibility_flag",
        "asos_fog_or_mist_flag",
        "asos_haze_code_flag",
        *UPWIND_FEATURE_COLS,
    ]

    summary = {
        "source_base_bundle": str(base),
        "asos_raw_root": str(raw_root),
        "rows_all": int(len(all_v7)),
        "asos_missing_rows_all": int(all_v7["asos_missing"].sum()),
        "asos_any_missing_rows_all": int(all_v7["asos_any_missing"].sum()),
        "low_visibility_rows_all": int(all_v7["asos_low_visibility_flag"].sum()),
        "very_low_visibility_rows_all": int(all_v7["asos_very_low_visibility_flag"].sum()),
        "fog_or_mist_rows_all": int(all_v7["asos_fog_or_mist_flag"].sum()),
        "upwind_edge_clipped_rows_all": int(all_v7["upwind_edge_clipped"].sum()),
        "variant_counts": variant_counts,
        "feature_columns": feature_columns,
        "excluded_features": ["AirKorea PM10/PM2.5"],
        "note": "ASOS values are historical observations; production inference needs forecast-compatible substitutes.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (metadata_dir / "upwind_visibility_bundle_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_readme(bundle_dir / "README.md")

    zip_path = bundle_dir.with_suffix(".zip")
    zip_dir(bundle_dir, zip_path)
    bundle_mb = sum(p.stat().st_size for p in bundle_dir.rglob("*") if p.is_file()) / 1024 / 1024
    summary.update(
        {
            "bundle_dir": str(bundle_dir),
            "zip_path": str(zip_path),
            "bundle_mb": round(bundle_mb, 2),
            "zip_mb": round(zip_path.stat().st_size / 1024 / 1024, 2),
        }
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
