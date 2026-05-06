"""Build a satellite training bundle for anomaly-filter comparison.

The bundle contains three daylight training variants:

- no_filter: operational daylight rows as-is
- mild_filter: removes conservative target anomaly candidates
- strong_filter: removes broader midday-low target candidates

Use this to compare whether filtering suspicious KPX proxy rows actually helps.
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
    parser.add_argument("--name", default="satellite_image_anomaly_compare_regions_2025")
    parser.add_argument("--val-start", default="2025-11-01")
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


def add_image_columns(samples: pd.DataFrame, sequences: pd.DataFrame) -> pd.DataFrame:
    seq = sequences[["sequence_index", "sequence_id", "image_path"]].copy()
    seq["image_file"] = seq["image_path"].map(basename_any_path)
    seq["image_rel_path"] = "images/" + seq["image_file"].astype(str)
    seq = seq.sort_values(["image_file", "sequence_index"]).reset_index(drop=True)
    seq["image_row"] = seq.groupby("image_file").cumcount().astype("int32")

    out = samples.merge(
        seq[["sequence_index", "sequence_id", "image_file", "image_rel_path", "image_row"]],
        on=["sequence_index", "sequence_id"],
        how="left",
    )
    if out["image_row"].isna().any():
        raise RuntimeError(f"image_row missing: {int(out['image_row'].isna().sum())}")
    out["image_row"] = out["image_row"].astype("int32")
    return out


def add_model_columns(samples: pd.DataFrame, *, val_start: str) -> pd.DataFrame:
    out = samples.copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])
    out["anchor_timestamp_kst"] = pd.to_datetime(out["anchor_timestamp_kst"])
    out["target_date_kst"] = out["target_timestamp_kst"].dt.strftime("%Y-%m-%d")
    out["split"] = np.where(out["target_timestamp_kst"] < pd.Timestamp(val_start), "train", "val")

    solar = out["solar_elevation"].astype(float)
    hour = out["hour"].astype(int)
    target = out["target_capacity_factor"].astype(float)

    out["target_cf"] = target.astype("float32")
    out["target_cf_clip_1p2"] = target.clip(0.0, 1.2).astype("float32")
    out["is_sun_up"] = solar > 0.0
    out["is_daylight_core"] = solar > 5.0
    out["is_daytime_hour"] = hour.between(8, 17)
    out["is_operational_daylight"] = out["is_daylight_core"] & out["is_daytime_hour"]
    out["is_peak_solar_hour"] = hour.between(10, 15) & (solar > 15.0)

    train_core = out[(out["split"] == "train") & out["is_operational_daylight"]].copy()
    stats = (
        train_core.groupby(["region", "hour"], dropna=False)["target_cf"]
        .agg(
            target_p05=lambda s: float(s.quantile(0.05)),
            target_p10=lambda s: float(s.quantile(0.10)),
            target_p25=lambda s: float(s.quantile(0.25)),
            target_p50="median",
            target_p75=lambda s: float(s.quantile(0.75)),
            target_p90=lambda s: float(s.quantile(0.90)),
            target_p95=lambda s: float(s.quantile(0.95)),
        )
        .reset_index()
    )
    out = out.merge(stats, on=["region", "hour"], how="left")
    stat_cols = ["target_p05", "target_p10", "target_p25", "target_p50", "target_p75", "target_p90", "target_p95"]
    out[stat_cols] = out[stat_cols].fillna(0.0).astype("float32")

    median = out["target_p50"].astype(float)
    p90 = out["target_p90"].astype(float)
    daylight = out["is_operational_daylight"]

    low_mild = (
        daylight
        & hour.between(10, 14)
        & (solar >= 18.0)
        & (median >= 0.25)
        & (target <= np.maximum(0.10, median * 0.30))
    )
    low_strong = (
        daylight
        & hour.between(9, 15)
        & (solar >= 15.0)
        & (median >= 0.25)
        & (target <= np.maximum(0.12, median * 0.45))
    )
    high_candidate = (
        daylight
        & (median <= 0.75)
        & (target >= np.minimum(1.05, p90 * 1.35))
    )

    out["anomaly_low_mild_candidate"] = low_mild
    out["anomaly_low_strong_candidate"] = low_strong
    out["anomaly_high_candidate"] = high_candidate
    out["anomaly_mild_candidate"] = low_mild | high_candidate
    out["anomaly_strong_candidate"] = low_strong | high_candidate

    base_weight = np.full(len(out), 0.03, dtype=np.float32)
    base_weight[out["is_sun_up"].to_numpy()] = 0.20
    base_weight[out["is_operational_daylight"].to_numpy()] = 1.00
    base_weight[out["is_peak_solar_hour"].to_numpy()] = 2.00
    out["sample_weight_operational"] = base_weight

    mild_weight = base_weight.copy()
    mild_weight[out["anomaly_mild_candidate"].to_numpy()] *= 0.35
    out["sample_weight_mild"] = mild_weight.astype("float32")

    strong_weight = base_weight.copy()
    strong_weight[out["anomaly_strong_candidate"].to_numpy()] *= 0.15
    out["sample_weight_strong"] = strong_weight.astype("float32")

    return out


def write_variant(metadata_dir: Path, daylight: pd.DataFrame, name: str, mask: pd.Series) -> dict[str, int]:
    variant = daylight[mask].copy()
    variant.to_parquet(metadata_dir / f"samples_daylight_{name}_all.parquet", index=False)

    train = variant[variant["split"] == "train"].copy()
    val = variant[variant["split"] == "val"].copy()
    train.to_parquet(metadata_dir / f"samples_daylight_{name}_train.parquet", index=False)
    val.to_parquet(metadata_dir / f"samples_daylight_{name}_val.parquet", index=False)

    horizon_dir = metadata_dir / "horizon" / name
    horizon_dir.mkdir(parents=True, exist_ok=True)
    for horizon in sorted(variant["horizon_hours"].astype(int).unique()):
        subset = variant[variant["horizon_hours"].astype(int) == horizon].copy()
        subset[subset["split"] == "train"].to_parquet(
            horizon_dir / f"samples_h{horizon}_train.parquet",
            index=False,
        )
        subset[subset["split"] == "val"].to_parquet(
            horizon_dir / f"samples_h{horizon}_val.parquet",
            index=False,
        )

    return {
        "all": int(len(variant)),
        "train": int(len(train)),
        "val": int(len(val)),
    }


def counts(frame: pd.DataFrame, columns: list[str]) -> dict[str, int]:
    result: dict[str, int] = {}
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        result["|".join(str(k) for k in keys)] = int(len(group))
    return result


def write_summary(samples: pd.DataFrame, variant_counts: dict[str, dict[str, int]], path: Path) -> None:
    daylight = samples[samples["is_operational_daylight"]].copy()
    top_anomaly_dates = (
        daylight[daylight["anomaly_strong_candidate"]]
        .groupby(["target_date_kst", "region"], dropna=False)
        .size()
        .sort_values(ascending=False)
        .head(25)
    )
    top_dict = {f"{date}|{region}": int(count) for (date, region), count in top_anomaly_dates.items()}

    summary = {
        "rows_total": int(len(samples)),
        "rows_daylight": int(len(daylight)),
        "variant_counts": variant_counts,
        "anomaly_counts": {
            "low_mild": int(samples["anomaly_low_mild_candidate"].sum()),
            "low_strong": int(samples["anomaly_low_strong_candidate"].sum()),
            "high": int(samples["anomaly_high_candidate"].sum()),
            "mild_any": int(samples["anomaly_mild_candidate"].sum()),
            "strong_any": int(samples["anomaly_strong_candidate"].sum()),
        },
        "strong_anomaly_by_split": counts(samples[samples["anomaly_strong_candidate"]], ["split"]),
        "strong_anomaly_by_region": counts(samples[samples["anomaly_strong_candidate"]], ["region"]),
        "strong_anomaly_by_hour": counts(samples[samples["anomaly_strong_candidate"]], ["hour"]),
        "top_strong_anomaly_dates": top_dict,
        "recommended_comparison": [
            "Train no_filter, mild_filter, and strong_filter with the same code and seed.",
            "Compare clean-val and real-val separately if you keep the original unfiltered val around.",
            "If strong_filter improves only filtered-val but not original-val, use it for analysis, not deployment.",
        ],
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme(path: Path) -> None:
    path.write_text(
        """# Satellite Anomaly Comparison Bundle

This bundle is for comparing target filtering levels.

Training variants:

- `samples_daylight_no_filter_train/val.parquet`
- `samples_daylight_mild_filter_train/val.parquet`
- `samples_daylight_strong_filter_train/val.parquet`

The original all-row table is:

- `metadata/samples_modeling_all_v4.parquet`

Use the same model, seed, and hyperparameters for each variant. Compare metrics
against both the filtered validation file and the original daylight validation
set if you want to know whether filtering only improves clean days.
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

    modeling = add_image_columns(samples, sequences)
    modeling = add_model_columns(modeling, val_start=args.val_start)
    modeling.to_parquet(metadata_dir / "samples_modeling_all_v4.parquet", index=False)

    daylight = modeling[modeling["is_operational_daylight"]].copy()
    variant_counts = {}
    variant_counts["no_filter"] = write_variant(
        metadata_dir,
        daylight,
        "no_filter",
        pd.Series(True, index=daylight.index),
    )
    variant_counts["mild_filter"] = write_variant(
        metadata_dir,
        daylight,
        "mild_filter",
        ~daylight["anomaly_mild_candidate"],
    )
    variant_counts["strong_filter"] = write_variant(
        metadata_dir,
        daylight,
        "strong_filter",
        ~daylight["anomaly_strong_candidate"],
    )

    write_summary(modeling, variant_counts, metadata_dir / "anomaly_compare_summary.json")
    write_readme(bundle_dir / "README.md")

    zip_path = bundle_dir.with_suffix(".zip")
    zip_dir(bundle_dir, zip_path)

    bundle_bytes = sum(p.stat().st_size for p in bundle_dir.rglob("*") if p.is_file())
    print(json.dumps(
        {
            "bundle_dir": str(bundle_dir),
            "zip_path": str(zip_path),
            "bundle_mb": round(bundle_bytes / 1024 / 1024, 2),
            "zip_mb": round(zip_path.stat().st_size / 1024 / 1024, 2),
            "variant_counts": variant_counts,
            "anomaly_mild": int(modeling["anomaly_mild_candidate"].sum()),
            "anomaly_strong": int(modeling["anomaly_strong_candidate"].sum()),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
