"""Package satellite image data with model-ready metadata.

The expensive GK2A NetCDF preprocessing already produced image shards and base
sample metadata. This script only derives safer training/evaluation metadata:

- relative image file names and npz row indices
- train/validation split
- daylight/core daylight/peak-hour flags
- robust sample weights
- conservative target anomaly candidate flags
- horizon-specific train/validation parquet files
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from datetime import datetime
from pathlib import Path, PureWindowsPath

import numpy as np
import pandas as pd


DEFAULT_INPUT = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data\processed\training"
    r"\satellite_image_clean_regions"
)
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\SSAFY\Project_Minsu\S305\server_upload")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--name", default="satellite_image_modeling_regions_2025")
    parser.add_argument("--val-start", default="2025-11-01")
    parser.add_argument("--core-solar-elevation", type=float, default=5.0)
    parser.add_argument("--peak-solar-elevation", type=float, default=15.0)
    return parser.parse_args()


def basename_any_path(path: object) -> str:
    text = str(path)
    if "\\" in text:
        return PureWindowsPath(text).name
    return Path(text).name


def copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def build_sequence_metadata(sequences: pd.DataFrame) -> pd.DataFrame:
    out = sequences.copy()
    out["image_file"] = out["image_path"].map(basename_any_path)
    out["image_rel_path"] = "images/" + out["image_file"].astype(str)

    row_index = out[["sequence_index", "sequence_id", "image_file"]].copy()
    row_index = row_index.sort_values(["image_file", "sequence_index"]).reset_index(drop=True)
    row_index["image_row"] = row_index.groupby("image_file").cumcount().astype("int32")

    out = out.merge(
        row_index[["sequence_index", "sequence_id", "image_row"]],
        on=["sequence_index", "sequence_id"],
        how="left",
    )
    return out


def add_modeling_columns(
    samples: pd.DataFrame,
    sequence_meta: pd.DataFrame,
    *,
    val_start: str,
    core_solar_elevation: float,
    peak_solar_elevation: float,
) -> pd.DataFrame:
    out = samples.copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])
    out["anchor_timestamp_kst"] = pd.to_datetime(out["anchor_timestamp_kst"])

    out = out.merge(
        sequence_meta[[
            "sequence_index",
            "sequence_id",
            "image_file",
            "image_rel_path",
            "image_row",
        ]],
        on=["sequence_index", "sequence_id"],
        how="left",
    )
    if out["image_row"].isna().any():
        missing = int(out["image_row"].isna().sum())
        raise RuntimeError(f"image_row merge failed for {missing} rows")

    out["image_row"] = out["image_row"].astype("int32")
    out["split"] = np.where(out["target_timestamp_kst"] < pd.Timestamp(val_start), "train", "val")

    solar_elevation = out["solar_elevation"].astype(float)
    hour = out["hour"].astype(int)
    horizon = out["horizon_hours"].astype(int)
    target = out["target_capacity_factor"].astype(float)

    out["target_cf"] = target.astype("float32")
    out["target_cf_clip_1p0"] = target.clip(0.0, 1.0).astype("float32")
    out["target_cf_clip_1p2"] = target.clip(0.0, 1.2).astype("float32")

    out["is_sun_up"] = solar_elevation > 0.0
    out["is_daylight_core"] = solar_elevation > core_solar_elevation
    out["is_daytime_hour"] = hour.between(8, 17)
    out["is_operational_daylight"] = out["is_daylight_core"] & out["is_daytime_hour"]
    out["is_peak_solar_hour"] = hour.between(10, 15) & (solar_elevation > peak_solar_elevation)
    out["is_twilight"] = out["is_sun_up"] & ~out["is_daylight_core"]

    # Production evaluation should not be dominated by trivial night zeros.
    weight = np.full(len(out), 0.03, dtype=np.float32)
    weight[out["is_twilight"].to_numpy()] = 0.20
    weight[out["is_operational_daylight"].to_numpy()] = 1.00
    weight[out["is_peak_solar_hour"].to_numpy()] = 2.00

    horizon_factor = horizon.map({1: 1.30, 2: 1.15, 3: 1.00, 6: 0.85}).fillna(1.0).to_numpy(dtype=np.float32)
    out["sample_weight_operational"] = (weight * horizon_factor).astype("float32")

    # Conservative target anomaly candidates. These are not deleted by default.
    # They are mainly for investigation and optional robust down-weighting.
    train_core = out[(out["split"] == "train") & out["is_operational_daylight"]].copy()
    stats = (
        train_core
        .groupby(["region", "hour"], dropna=False)["target_cf"]
        .agg(
            target_p05=lambda s: float(s.quantile(0.05)),
            target_p10=lambda s: float(s.quantile(0.10)),
            target_p50="median",
            target_p90=lambda s: float(s.quantile(0.90)),
            target_p95=lambda s: float(s.quantile(0.95)),
        )
        .reset_index()
    )

    out = out.merge(stats, on=["region", "hour"], how="left")
    out[["target_p05", "target_p10", "target_p50", "target_p90", "target_p95"]] = (
        out[["target_p05", "target_p10", "target_p50", "target_p90", "target_p95"]]
        .fillna(0.0)
        .astype("float32")
    )

    midday = hour.between(10, 14) & (solar_elevation >= 20.0)
    high_sun = solar_elevation >= 25.0
    very_low_target = target <= np.maximum(0.08, out["target_p10"].astype(float) * 0.55)
    very_high_target = target >= np.minimum(1.05, out["target_p90"].astype(float) * 1.35)

    out["anomaly_midday_low_candidate"] = (
        out["is_operational_daylight"] & midday & high_sun & very_low_target & (out["target_p50"] >= 0.25)
    )
    out["anomaly_high_target_candidate"] = (
        out["is_operational_daylight"] & very_high_target & (out["target_p50"] <= 0.75)
    )
    out["anomaly_target_candidate"] = (
        out["anomaly_midday_low_candidate"] | out["anomaly_high_target_candidate"]
    )

    robust_weight = out["sample_weight_operational"].to_numpy(dtype=np.float32).copy()
    robust_weight[out["anomaly_target_candidate"].to_numpy()] *= 0.35
    out["sample_weight_robust"] = robust_weight.astype("float32")

    out["model_split_daylight"] = np.where(
        out["is_operational_daylight"],
        out["split"],
        "ignore",
    )
    out["model_split_daylight_robust"] = np.where(
        out["is_operational_daylight"] & ~out["anomaly_target_candidate"],
        out["split"],
        "ignore",
    )

    return out


def write_partition_files(samples: pd.DataFrame, metadata_dir: Path) -> None:
    daylight = samples[samples["is_operational_daylight"]].copy()
    robust = samples[samples["is_operational_daylight"] & ~samples["anomaly_target_candidate"]].copy()

    daylight.to_parquet(metadata_dir / "samples_daylight_all.parquet", index=False)
    daylight[daylight["split"] == "train"].to_parquet(
        metadata_dir / "samples_daylight_train.parquet",
        index=False,
    )
    daylight[daylight["split"] == "val"].to_parquet(
        metadata_dir / "samples_daylight_val.parquet",
        index=False,
    )

    robust.to_parquet(metadata_dir / "samples_daylight_robust_all.parquet", index=False)
    robust[robust["split"] == "train"].to_parquet(
        metadata_dir / "samples_daylight_robust_train.parquet",
        index=False,
    )
    robust[robust["split"] == "val"].to_parquet(
        metadata_dir / "samples_daylight_robust_val.parquet",
        index=False,
    )

    horizon_dir = metadata_dir / "horizon"
    horizon_dir.mkdir(exist_ok=True)
    for horizon in sorted(samples["horizon_hours"].astype(int).unique()):
        subset = samples[samples["horizon_hours"].astype(int) == horizon].copy()
        subset.to_parquet(horizon_dir / f"samples_h{horizon}_all.parquet", index=False)
        subset[subset["split"] == "train"].to_parquet(
            horizon_dir / f"samples_h{horizon}_train.parquet",
            index=False,
        )
        subset[subset["split"] == "val"].to_parquet(
            horizon_dir / f"samples_h{horizon}_val.parquet",
            index=False,
        )

        daylight_h = daylight[daylight["horizon_hours"].astype(int) == horizon].copy()
        daylight_h[daylight_h["split"] == "train"].to_parquet(
            horizon_dir / f"samples_h{horizon}_daylight_train.parquet",
            index=False,
        )
        daylight_h[daylight_h["split"] == "val"].to_parquet(
            horizon_dir / f"samples_h{horizon}_daylight_val.parquet",
            index=False,
        )


def counts(frame: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        result["|".join(str(k) for k in keys)] = int(len(group))
    return result


def write_summary(samples: pd.DataFrame, path: Path) -> None:
    daylight = samples[samples["is_operational_daylight"]]
    robust = daylight[~daylight["anomaly_target_candidate"]]

    summary = {
        "rows_total": int(len(samples)),
        "rows_by_split": counts(samples, ["split"]),
        "rows_daylight_by_split": counts(daylight, ["split"]),
        "rows_daylight_robust_by_split": counts(robust, ["split"]),
        "rows_by_region": counts(samples, ["region"]),
        "rows_daylight_by_region": counts(daylight, ["region"]),
        "rows_by_horizon": counts(samples, ["horizon_hours"]),
        "rows_daylight_by_horizon": counts(daylight, ["horizon_hours"]),
        "anomaly_candidates": {
            "midday_low": int(samples["anomaly_midday_low_candidate"].sum()),
            "high_target": int(samples["anomaly_high_target_candidate"].sum()),
            "any": int(samples["anomaly_target_candidate"].sum()),
        },
        "target_cf": {
            "all": {
                "min": float(samples["target_cf"].min()),
                "max": float(samples["target_cf"].max()),
                "mean": float(samples["target_cf"].mean()),
            },
            "daylight": {
                "min": float(daylight["target_cf"].min()),
                "max": float(daylight["target_cf"].max()),
                "mean": float(daylight["target_cf"].mean()),
            },
        },
        "recommended_files": {
            "baseline_all_hours": "metadata/samples_modeling_all_v3.parquet",
            "daylight": "metadata/samples_daylight_train.parquet + samples_daylight_val.parquet",
            "daylight_robust": "metadata/samples_daylight_robust_train.parquet + samples_daylight_robust_val.parquet",
            "horizon_specific": "metadata/horizon/samples_h{1,2,3,6}_daylight_train.parquet",
        },
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme(path: Path) -> None:
    path.write_text(
        """# Satellite Modeling Regions 2025 Bundle

This bundle is model-ready and keeps image paths Linux-friendly.

## Important files

- `images/images_2025_MM.npz`: uint8 image tensors.
- `metadata/sequences_all_v3.parquet`: sequence metadata with `image_file`, `image_rel_path`, `image_row`.
- `metadata/samples_modeling_all_v3.parquet`: all rows with split, image row, daylight flags, weights, and anomaly candidates.
- `metadata/samples_daylight_train.parquet`, `samples_daylight_val.parquet`: operational daylight rows.
- `metadata/samples_daylight_robust_train.parquet`, `samples_daylight_robust_val.parquet`: daylight rows excluding conservative target anomaly candidates.
- `metadata/horizon/`: horizon-specific train/val parquet files.
- `metadata/modeling_summary.json`: counts and recommended usage.

## Recommended next experiments

1. Train daylight model on `samples_daylight_train/val`.
2. Train robust daylight model on `samples_daylight_robust_train/val`.
3. Train horizon-specific models for 1h/2h/3h/6h.
4. Compare daylight-only metrics, not all-hour metrics dominated by night zeros.

For production inference, return 0 when `solar_elevation <= 0`.
""",
        encoding="utf-8",
    )


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in sorted(src_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, file_path.relative_to(src_dir.parent))


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_root = args.output_root.resolve()

    for required in [
        input_dir / "images",
        input_dir / "metadata" / "samples_all.parquet",
        input_dir / "metadata" / "sequences_all.parquet",
        input_dir / "manifest.json",
    ]:
        if not required.exists():
            raise FileNotFoundError(required)

    output_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_dir = output_root / f"{args.name}_{timestamp}"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    bundle_dir.mkdir(parents=True)

    copy_dir(input_dir / "images", bundle_dir / "images")
    copy_dir(input_dir / "metadata", bundle_dir / "metadata")
    shutil.copy2(input_dir / "manifest.json", bundle_dir / "manifest.json")

    metadata_dir = bundle_dir / "metadata"
    samples = pd.read_parquet(input_dir / "metadata" / "samples_all.parquet")
    sequences = pd.read_parquet(input_dir / "metadata" / "sequences_all.parquet")

    sequence_meta = build_sequence_metadata(sequences)
    sequence_meta.to_parquet(metadata_dir / "sequences_all_v3.parquet", index=False)

    modeling = add_modeling_columns(
        samples,
        sequence_meta,
        val_start=args.val_start,
        core_solar_elevation=args.core_solar_elevation,
        peak_solar_elevation=args.peak_solar_elevation,
    )
    modeling.to_parquet(metadata_dir / "samples_modeling_all_v3.parquet", index=False)
    write_partition_files(modeling, metadata_dir)
    write_summary(modeling, metadata_dir / "modeling_summary.json")
    write_readme(bundle_dir / "README.md")

    zip_path = bundle_dir.with_suffix(".zip")
    zip_dir(bundle_dir, zip_path)

    daylight = modeling[modeling["is_operational_daylight"]]
    robust = daylight[~daylight["anomaly_target_candidate"]]
    bundle_bytes = sum(p.stat().st_size for p in bundle_dir.rglob("*") if p.is_file())

    print(json.dumps(
        {
            "bundle_dir": str(bundle_dir),
            "zip_path": str(zip_path),
            "bundle_mb": round(bundle_bytes / 1024 / 1024, 2),
            "zip_mb": round(zip_path.stat().st_size / 1024 / 1024, 2),
            "rows_total": int(len(modeling)),
            "rows_daylight": int(len(daylight)),
            "rows_daylight_train": int((daylight["split"] == "train").sum()),
            "rows_daylight_val": int((daylight["split"] == "val").sum()),
            "rows_daylight_robust": int(len(robust)),
            "anomaly_candidates": int(modeling["anomaly_target_candidate"].sum()),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
