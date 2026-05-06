"""Build a GPU-server upload bundle for daylight-focused satellite training.

This does not rerun NetCDF preprocessing. It reuses the existing image shards
and adds derived metadata files for daylight-only and weighted training.
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


DEFAULT_INPUT = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data\processed\training"
    r"\satellite_image_clean_regions"
)
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\SSAFY\Project_Minsu\S305\server_upload")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--name",
        default="satellite_image_daylight_regions_2025",
        help="Base bundle directory name. A timestamp suffix is appended.",
    )
    parser.add_argument("--daylight-elevation", type=float, default=5.0)
    parser.add_argument("--val-start", default="2025-11-01")
    return parser.parse_args()


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def add_training_columns(
    samples: pd.DataFrame,
    *,
    daylight_elevation: float,
    val_start: str,
) -> pd.DataFrame:
    out = samples.copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])
    out["split"] = np.where(
        out["target_timestamp_kst"] < pd.Timestamp(val_start),
        "train",
        "val",
    )

    solar_elevation = out["solar_elevation"].astype(float)
    hour = out["hour"].astype(int)

    out["is_sun_up"] = solar_elevation > 0
    out["is_daylight_strict"] = solar_elevation > daylight_elevation
    out["is_daytime_hour"] = hour.between(8, 17)
    out["is_peak_solar_hour"] = hour.between(10, 15)
    out["is_daylight_eval"] = out["is_daylight_strict"] & out["is_daytime_hour"]

    weight = np.full(len(out), 0.05, dtype=np.float32)
    weight[out["is_sun_up"].to_numpy()] = 0.25
    weight[out["is_daylight_strict"].to_numpy()] = 1.0
    weight[out["is_peak_solar_hour"].to_numpy() & out["is_daylight_strict"].to_numpy()] = 2.0
    out["sample_weight_daylight"] = weight

    return out


def write_summary(samples: pd.DataFrame, path: Path) -> None:
    def counts(frame: pd.DataFrame, cols: list[str]) -> dict:
        result = {}
        for keys, group in frame.groupby(cols, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            key = "|".join(str(k) for k in keys)
            result[key] = int(len(group))
        return result

    summary = {
        "rows_total": int(len(samples)),
        "rows_by_split": counts(samples, ["split"]),
        "rows_daylight_eval_by_split": counts(samples[samples["is_daylight_eval"]], ["split"]),
        "rows_daylight_strict_by_split": counts(samples[samples["is_daylight_strict"]], ["split"]),
        "rows_by_region": counts(samples, ["region"]),
        "rows_by_horizon": counts(samples, ["horizon_hours"]),
        "target_capacity_factor": {
            "min": float(samples["target_capacity_factor"].min()),
            "max": float(samples["target_capacity_factor"].max()),
            "mean": float(samples["target_capacity_factor"].mean()),
        },
        "notes": [
            "Raw GK2A NetCDF preprocessing was not rerun.",
            "Use samples_daylight_train/val for daylight-only experiments.",
            "Use samples_all_v2 with sample_weight_daylight for weighted all-hours training.",
            "For inference, clamp output to zero when solar_elevation <= 0.",
        ],
    }
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def write_readme(path: Path, *, daylight_elevation: float, val_start: str) -> None:
    text = f"""# Satellite Image Daylight Training Bundle

This bundle reuses the existing satellite image shards. It does not rerun raw
GK2A NetCDF preprocessing.

## Data

- `images/images_2025_MM.npz`: uint8 tensors.
- `metadata/sequences_all.parquet`: sequence metadata.
- `metadata/samples_all.parquet`: original sample metadata.
- `metadata/samples_all_v2.parquet`: original samples plus split and daylight columns.
- `metadata/samples_daylight_all.parquet`: `solar_elevation > {daylight_elevation}`.
- `metadata/samples_daylight_train.parquet`: daylight rows before `{val_start}`.
- `metadata/samples_daylight_val.parquet`: daylight rows from `{val_start}` onward.
- `metadata/daylight_summary.json`: counts and target summary.

## Recommended training

Train the next model against daylight metrics, because all-hour metrics are
dominated by night rows that are trivially zero.

Two practical options:

1. Daylight-only training/evaluation:
   use `samples_daylight_train.parquet` and `samples_daylight_val.parquet`.
2. Weighted all-hour training:
   use `samples_all_v2.parquet` and multiply per-row loss by
   `sample_weight_daylight`.

For production inference, return 0 when `solar_elevation <= 0`, then run the
model only for daylight/twilight cases.
"""
    path.write_text(text, encoding="utf-8")


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

    if not input_dir.exists():
        raise FileNotFoundError(input_dir)

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

    copy_tree(input_dir / "images", bundle_dir / "images")
    copy_tree(input_dir / "metadata", bundle_dir / "metadata")
    shutil.copy2(input_dir / "manifest.json", bundle_dir / "manifest.json")

    samples_path = bundle_dir / "metadata" / "samples_all.parquet"
    samples = pd.read_parquet(samples_path)
    samples_v2 = add_training_columns(
        samples,
        daylight_elevation=args.daylight_elevation,
        val_start=args.val_start,
    )

    metadata_dir = bundle_dir / "metadata"
    samples_v2.to_parquet(metadata_dir / "samples_all_v2.parquet", index=False)

    daylight = samples_v2[samples_v2["is_daylight_strict"]].copy()
    daylight.to_parquet(metadata_dir / "samples_daylight_all.parquet", index=False)
    daylight[daylight["split"] == "train"].to_parquet(
        metadata_dir / "samples_daylight_train.parquet",
        index=False,
    )
    daylight[daylight["split"] == "val"].to_parquet(
        metadata_dir / "samples_daylight_val.parquet",
        index=False,
    )

    write_summary(samples_v2, metadata_dir / "daylight_summary.json")
    write_readme(
        bundle_dir / "README.md",
        daylight_elevation=args.daylight_elevation,
        val_start=args.val_start,
    )

    zip_path = bundle_dir.with_suffix(".zip")
    zip_dir(bundle_dir, zip_path)

    bundle_bytes = sum(p.stat().st_size for p in bundle_dir.rglob("*") if p.is_file())
    zip_bytes = zip_path.stat().st_size

    print(json.dumps(
        {
            "bundle_dir": str(bundle_dir),
            "zip_path": str(zip_path),
            "bundle_mb": round(bundle_bytes / 1024 / 1024, 2),
            "zip_mb": round(zip_bytes / 1024 / 1024, 2),
            "rows_total": int(len(samples_v2)),
            "rows_daylight_total": int(len(daylight)),
            "rows_daylight_train": int((daylight["split"] == "train").sum()),
            "rows_daylight_val": int((daylight["split"] == "val").sum()),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
