"""Build satellite training bundle with safe KMA ASOS wind/weather features.

This reuses the v4 satellite anomaly comparison bundle and merges hourly ASOS
observations by `(region, target_timestamp_kst)`. The resulting bundle is meant
for GPU experiments that compare satellite-only against satellite+wind/weather.

Only the stable leading numeric ASOS columns are used here. Later ASOS fields
include variable text weather/cloud tokens, so whitespace parsing can shift
cloud, sunshine, radiation, and visibility columns.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BASE_BUNDLE = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\server_upload"
    r"\satellite_image_anomaly_compare_regions_2025_20260506_171847"
)
DEFAULT_ASOS_FEATURES = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data\processed\weather"
    r"\kma_asos_apihub\kma_asos_hourly_region_features_2025.parquet"
)
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\SSAFY\Project_Minsu\S305\server_upload")

VARIANTS = ("no_filter", "mild_filter", "strong_filter")
SAFE_ASOS_SOURCE_COLS = ["WD", "WS", "TA", "HM", "RN"]
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
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-bundle", type=Path, default=DEFAULT_BASE_BUNDLE)
    parser.add_argument("--asos-features", type=Path, default=DEFAULT_ASOS_FEATURES)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--name", default="satellite_image_wind_safe_regions_2025")
    return parser.parse_args()


def copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def load_asos_features(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)

    asos = pd.read_parquet(path)
    asos["target_timestamp_kst"] = pd.to_datetime(asos["timestamp_kst"])
    keep_cols = ["target_timestamp_kst", "region", "station_id", "station_name", *SAFE_ASOS_SOURCE_COLS]
    missing = [col for col in keep_cols if col not in asos.columns]
    if missing:
        raise RuntimeError(f"ASOS feature columns missing: {missing}")

    out = asos[keep_cols].copy()
    out = out.rename(
        columns={
            "station_id": "asos_station_id",
            "station_name": "asos_station_name",
            "WD": "asos_wd_code",
            "WS": "wind_speed_ms",
            "TA": "asos_ta",
            "HM": "asos_hm",
            "RN": "asos_rn",
        }
    )

    numeric_cols = ["asos_wd_code", "wind_speed_ms", "asos_ta", "asos_hm", "asos_rn"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        out.loc[out[col] <= -900, col] = np.nan

    out.loc[out["asos_wd_code"] < 0, "asos_wd_code"] = np.nan
    out.loc[out["wind_speed_ms"] < 0, "wind_speed_ms"] = np.nan
    out.loc[out["asos_hm"] < 0, "asos_hm"] = np.nan
    # KMA ASOS commonly marks no hourly precipitation as -9. Use 0 mm so rain
    # does not become an artificial missing-value median feature.
    out.loc[out["asos_rn"] < 0, "asos_rn"] = 0.0

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

    return out


def add_wind_features(frame: pd.DataFrame, asos: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])

    merged = out.merge(
        asos,
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

    # Scaled versions for simple neural-network tabular inputs.
    merged["wind_u_scaled"] = (merged["wind_u"] / 15.0).astype("float32")
    merged["wind_v_scaled"] = (merged["wind_v"] / 15.0).astype("float32")
    merged["wind_speed_scaled"] = (merged["wind_speed_ms"] / 15.0).astype("float32")
    merged["asos_ta_scaled"] = ((merged["asos_ta"] + 30.0) / 70.0).astype("float32")
    merged["asos_hm_scaled"] = (merged["asos_hm"] / 100.0).astype("float32")
    merged["asos_rn_log1p"] = np.log1p(np.clip(merged["asos_rn"].to_numpy(dtype=float), 0, None)).astype("float32")

    return merged


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
        subset[subset["split"] == "train"].to_parquet(
            horizon_dir / f"samples_h{horizon}_train.parquet",
            index=False,
        )
        subset[subset["split"] == "val"].to_parquet(
            horizon_dir / f"samples_h{horizon}_val.parquet",
            index=False,
        )

    return {
        "all": int(len(all_frame)),
        "train": int(len(train)),
        "val": int(len(val)),
        "asos_missing_rows": int(all_frame["asos_missing"].sum()),
        "asos_any_missing_rows": int(all_frame["asos_any_missing"].sum()),
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
        """# Satellite + KMA ASOS Safe Wind Bundle

This bundle reuses the satellite anomaly comparison v4 image shards and adds
2025 KMA APIHub ASOS hourly observation features.

Important metadata files:

- `metadata/samples_modeling_all_wind_safe_v6.parquet`
- `metadata/samples_daylight_no_filter_train/val.parquet`
- `metadata/samples_daylight_mild_filter_train/val.parquet`
- `metadata/samples_daylight_strong_filter_train/val.parquet`
- `metadata/horizon/{variant}/samples_h{1,2,3,6}_train/val.parquet`

Wind/weather columns include:

- `wind_u`, `wind_v`, `wind_speed_ms`, `wind_dir_deg`
- `wind_dir_sin`, `wind_dir_cos`
- `asos_ta`, `asos_hm`, `asos_rn`
- scaled columns with `_scaled` or `_log1p` suffixes

Cloud/sunshine/radiation/visibility ASOS columns are intentionally excluded.
The raw ASOS text format has variable text weather/cloud fields that can shift
those columns when parsed by whitespace.

These are historical observations, not forecast archive values. Use them first
to test whether wind/weather helps. Production inference must use KMA forecast
features such as `UUU`, `VVV`, `VEC`, `WSD`, `SKY`, `PTY`, `RN1`, `REH`, `T1H`.
""",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    base = args.base_bundle.resolve()
    output_root = args.output_root.resolve()
    asos = load_asos_features(args.asos_features.resolve())

    for required in [base / "images", base / "metadata" / "samples_modeling_all_v4.parquet"]:
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
    all_v4 = pd.read_parquet(base / "metadata" / "samples_modeling_all_v4.parquet")
    all_wind = add_wind_features(all_v4, asos)
    all_wind.to_parquet(metadata_dir / "samples_modeling_all_wind_safe_v6.parquet", index=False)

    variant_counts: dict[str, dict[str, int]] = {}
    for variant in VARIANTS:
        path = base / "metadata" / f"samples_daylight_{variant}_all.parquet"
        frame = pd.read_parquet(path)
        frame_wind = add_wind_features(frame, asos)
        variant_counts[variant] = write_variant_files(metadata_dir, variant, frame_wind)

    summary = {
        "source_base_bundle": str(base),
        "asos_features": str(args.asos_features.resolve()),
        "rows_all": int(len(all_wind)),
        "asos_missing_rows_all": int(all_wind["asos_missing"].sum()),
        "asos_any_missing_rows_all": int(all_wind["asos_any_missing"].sum()),
        "variant_counts": variant_counts,
        "wind_feature_columns": [
            "wind_u_scaled",
            "wind_v_scaled",
            "wind_speed_scaled",
            "wind_dir_sin",
            "wind_dir_cos",
            "asos_ta_scaled",
            "asos_hm_scaled",
            "asos_rn_log1p",
        ],
        "excluded_asos_columns": ["CA_TOT", "CA_MID", "SS", "SI", "VS"],
        "note": "ASOS values are historical observations; use KMA forecast features for production inference.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (metadata_dir / "wind_bundle_summary.json").write_text(
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
