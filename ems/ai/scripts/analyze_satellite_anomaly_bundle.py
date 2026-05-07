"""Analyze the satellite anomaly comparison bundle.

This is a data-only check. It does not load a trained model. The goal is to
verify whether horizon metrics are being compared on similarly distributed
validation rows, and how much each anomaly filter changes the data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BUNDLE = Path(
    r"C:\Users\SSAFY\Project_Minsu\S305\server_upload"
    r"\satellite_image_anomaly_compare_regions_2025_20260506_171847"
)
DEFAULT_OUTPUT = Path(
    r"C:\Users\SSAFY\PycharmProjects\S14P31S305\ems\ai\outputs"
    r"\satellite_anomaly_compare_v4_data_check"
)
VARIANTS = ("no_filter", "mild_filter", "strong_filter")
KEY_COLS = ["sequence_id", "target_timestamp_kst", "region", "horizon_hours"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle-dir", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_variant(bundle_dir: Path, variant: str, split: str) -> pd.DataFrame:
    path = bundle_dir / "metadata" / f"samples_daylight_{variant}_{split}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_parquet(path)
    df["target_timestamp_kst"] = pd.to_datetime(df["target_timestamp_kst"])
    df["target_date_kst"] = df["target_timestamp_kst"].dt.strftime("%Y-%m-%d")
    df["variant"] = variant
    df["split"] = split
    return df


def summarize_group(df: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return (
        df.groupby(by, dropna=False)
        .agg(
            rows=("target_capacity_factor", "size"),
            target_mean=("target_capacity_factor", "mean"),
            target_std=("target_capacity_factor", "std"),
            target_min=("target_capacity_factor", "min"),
            target_max=("target_capacity_factor", "max"),
            hour_mean=("hour", "mean"),
            solar_elevation_mean=("solar_elevation", "mean"),
            peak_hour_share=("is_peak_solar_hour", "mean"),
            anomaly_mild_share=("anomaly_mild_candidate", "mean"),
            anomaly_strong_share=("anomaly_strong_candidate", "mean"),
        )
        .reset_index()
    )


def full_horizon_rows(df: pd.DataFrame) -> pd.DataFrame:
    horizons = {1, 2, 3, 6}
    group_cols = ["region", "target_timestamp_kst"]
    horizon_sets = (
        df.groupby(group_cols, dropna=False)["horizon_hours"]
        .apply(lambda s: frozenset(int(x) for x in s))
        .reset_index(name="horizon_set")
    )
    complete = horizon_sets[horizon_sets["horizon_set"] == horizons][group_cols]
    return df.merge(complete, on=group_cols, how="inner")


def key_frame(df: pd.DataFrame) -> pd.DataFrame:
    out = df[KEY_COLS].copy()
    out["horizon_hours"] = out["horizon_hours"].astype(int)
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])
    return out.drop_duplicates()


def removed_rows(source: pd.DataFrame, kept: pd.DataFrame) -> pd.DataFrame:
    source_key = key_frame(source)
    kept_key = key_frame(kept)
    merged = source_key.merge(kept_key, on=KEY_COLS, how="left", indicator=True)
    removed_key = merged[merged["_merge"] == "left_only"][KEY_COLS]
    return source.merge(removed_key, on=KEY_COLS, how="inner")


def write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    view = df if max_rows is None else df.head(max_rows)
    if view.empty:
        return "_No rows._"

    columns = [str(col) for col in view.columns]
    rows: list[list[str]] = []
    for _, row in view.iterrows():
        values: list[str] = []
        for col in view.columns:
            value = row[col]
            if isinstance(value, float):
                values.append(f"{value:.5f}")
            else:
                values.append(str(value))
        rows.append(values)

    widths = [
        max(len(columns[idx]), *(len(row[idx]) for row in rows))
        for idx in range(len(columns))
    ]

    def fmt(values: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[idx]) for idx, value in enumerate(values)) + " |"

    header = fmt(columns)
    separator = "| " + " | ".join("-" * width for width in widths) + " |"
    body = [fmt(row) for row in rows]
    return "\n".join([header, separator, *body])


def main() -> None:
    args = parse_args()
    bundle_dir = args.bundle_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    frames: dict[tuple[str, str], pd.DataFrame] = {}
    for variant in VARIANTS:
        for split in ("train", "val"):
            frames[(variant, split)] = load_variant(bundle_dir, variant, split)

    all_rows = pd.concat(frames.values(), ignore_index=True)
    variant_counts = (
        all_rows.groupby(["variant", "split"], dropna=False)
        .size()
        .reset_index(name="rows")
    )

    horizon_summary = summarize_group(all_rows, ["variant", "split", "horizon_hours"])
    val_horizon_summary = horizon_summary[horizon_summary["split"] == "val"].copy()
    val_hour_horizon = (
        all_rows[all_rows["split"] == "val"]
        .groupby(["variant", "horizon_hours", "hour"], dropna=False)
        .size()
        .reset_index(name="rows")
    )
    val_region_horizon = (
        all_rows[all_rows["split"] == "val"]
        .groupby(["variant", "horizon_hours", "region"], dropna=False)
        .size()
        .reset_index(name="rows")
    )

    fair_frames = []
    fair_counts = []
    fair_horizon_summary_parts = []
    for variant in VARIANTS:
        fair = full_horizon_rows(frames[(variant, "val")])
        fair_frames.append(fair.assign(variant=variant))
        group_count = fair[["region", "target_timestamp_kst"]].drop_duplicates().shape[0]
        fair_counts.append(
            {
                "variant": variant,
                "fair_target_groups": int(group_count),
                "fair_rows": int(len(fair)),
                "original_val_rows": int(len(frames[(variant, "val")])),
                "coverage_share": float(len(fair) / len(frames[(variant, "val")])),
            }
        )
        fair_horizon_summary_parts.append(
            summarize_group(fair.assign(variant=variant, split="val_fair"), ["variant", "horizon_hours"])
        )

    fair_all = pd.concat(fair_frames, ignore_index=True)
    fair_counts_df = pd.DataFrame(fair_counts)
    fair_horizon_summary = pd.concat(fair_horizon_summary_parts, ignore_index=True)

    no_val = frames[("no_filter", "val")]
    mild_val = frames[("mild_filter", "val")]
    strong_val = frames[("strong_filter", "val")]
    mild_removed_val = removed_rows(no_val, mild_val)
    strong_removed_val = removed_rows(no_val, strong_val)

    removal_summary_parts = []
    for name, removed in [("mild_filter", mild_removed_val), ("strong_filter", strong_removed_val)]:
        if removed.empty:
            continue
        by_region = (
            removed.groupby(["region"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values("rows", ascending=False)
        )
        by_region.insert(0, "filter", name)
        by_hour = (
            removed.groupby(["hour"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values("rows", ascending=False)
        )
        by_hour.insert(0, "filter", name)
        by_horizon = (
            removed.groupby(["horizon_hours"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values("horizon_hours")
        )
        by_horizon.insert(0, "filter", name)
        by_date = (
            removed.groupby(["target_date_kst", "region"], dropna=False)
            .size()
            .reset_index(name="rows")
            .sort_values("rows", ascending=False)
            .head(30)
        )
        by_date.insert(0, "filter", name)
        removal_summary_parts.extend(
            [
                ("removed_by_region", by_region),
                ("removed_by_hour", by_hour),
                ("removed_by_horizon", by_horizon),
                ("removed_top_dates", by_date),
            ]
        )

    write_csv(variant_counts, output_dir / "variant_counts.csv")
    write_csv(horizon_summary, output_dir / "horizon_summary.csv")
    write_csv(val_horizon_summary, output_dir / "val_horizon_summary.csv")
    write_csv(val_hour_horizon, output_dir / "val_hour_horizon_counts.csv")
    write_csv(val_region_horizon, output_dir / "val_region_horizon_counts.csv")
    write_csv(fair_counts_df, output_dir / "fair_horizon_counts.csv")
    write_csv(fair_horizon_summary, output_dir / "fair_horizon_summary.csv")
    write_csv(fair_all, output_dir / "fair_val_rows.csv")
    write_csv(mild_removed_val, output_dir / "mild_removed_val_rows.csv")
    write_csv(strong_removed_val, output_dir / "strong_removed_val_rows.csv")
    for name, df in removal_summary_parts:
        write_csv(df, output_dir / f"{name}.csv")

    summary = {
        "bundle_dir": str(bundle_dir),
        "output_dir": str(output_dir),
        "variant_counts": variant_counts.to_dict(orient="records"),
        "fair_counts": fair_counts_df.to_dict(orient="records"),
        "removed_val_rows": {
            "mild_filter": int(len(mild_removed_val)),
            "strong_filter": int(len(strong_removed_val)),
        },
        "note": (
            "This is a data-only check. Model metrics still need a separate "
            "cross-evaluation of the strong_filter checkpoint on no_filter validation."
        ),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = f"""# Satellite Anomaly Compare v4 Data Check

## Scope

This report checks validation-data composition only. It does not load the GPU
checkpoint.

Bundle:

```text
{bundle_dir}
```

## Variant Counts

{markdown_table(variant_counts)}

## Validation Horizon Summary

{markdown_table(val_horizon_summary)}

## Fair Horizon Coverage

Rows where each `(region, target_timestamp_kst)` has all horizons `1, 2, 3, 6`.

{markdown_table(fair_counts_df)}

## Fair Horizon Target Summary

{markdown_table(fair_horizon_summary)}

## Removed Validation Rows

Mild removed rows: `{len(mild_removed_val)}`

Strong removed rows: `{len(strong_removed_val)}`

## Interpretation

- If fair horizon summaries still show 1h has higher target variance or more
  peak-hour rows, horizon RMSE comparison is not apples-to-apples.
- If fair horizon summaries are similar but 1h remains worse, likely causes are
  KPX proxy timing/noise and missing future cloud-motion or wind features.
- The model checkpoint should next be evaluated across both filtered-val and
  original no-filter val to separate clean-day performance from real-val risk.
"""
    (output_dir / "README.md").write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
