"""Evaluate a satellite CNN checkpoint on another validation variant.

Intended GPU-server usage:

python ems/ai/scripts/evaluate_satellite_checkpoint_crossval.py \
  --data-dir /home/j-k14s305/s305-work/satellite_image_anomaly_compare_regions_2025_20260506_171847 \
  --checkpoint /home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter/best_model.pt \
  --variant no_filter

This separates clean-val performance from real-val risk by evaluating the
strong_filter checkpoint on the original no_filter validation rows.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


DEFAULT_DATA_DIR = Path(
    "/home/j-k14s305/s305-work/satellite_image_anomaly_compare_regions_2025_20260506_171847"
)
DEFAULT_CHECKPOINT = Path(
    "/home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter/best_model.pt"
)
DEFAULT_OUTPUT_DIR = Path(
    "/home/j-k14s305/s305-work/runs/satellite_anomaly_compare_v4/strong_filter_cross_eval"
)
DEFAULT_NUM_COLS = [
    "cap_scaled",
    "solar_elev_scaled",
    "is_daylight",
    "hour_scaled",
    "doy_scaled",
    "month_scaled",
    "hour_of_day_sin",
    "hour_of_day_cos",
    "day_of_year_sin",
    "day_of_year_cos",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--variant", default="no_filter")
    parser.add_argument("--batch-size", type=int, default=4096)
    parser.add_argument("--num-workers", type=int, default=16)
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return parser.parse_args()


def normalize_horizon_map(raw: dict) -> dict[int, int]:
    return {int(key): int(value) for key, value in raw.items()}


def prepare_frame(
    frame: pd.DataFrame,
    *,
    region_map: dict[str, int],
    horizon_map: dict[int, int],
) -> pd.DataFrame:
    out = frame.copy()
    out["target_timestamp_kst"] = pd.to_datetime(out["target_timestamp_kst"])
    out["region_id"] = out["region"].map(region_map).astype("int64")
    out["horizon_id"] = out["horizon_hours"].astype(int).map(horizon_map).astype("int64")
    out["cap_scaled"] = out["estimated_capacity_kw"].astype(float) / 300000.0
    out["solar_elev_scaled"] = out["solar_elevation"].astype(float) / 90.0
    out["hour_scaled"] = out["hour"].astype(float) / 23.0
    out["doy_scaled"] = out["day_of_year"].astype(float) / 366.0
    out["month_scaled"] = out["month"].astype(float) / 12.0
    out["is_daylight"] = out["is_daylight"].astype(float)
    return out


def fair_horizon_rows(frame: pd.DataFrame) -> pd.DataFrame:
    horizons = {1, 2, 3, 6}
    group_cols = ["region", "target_timestamp_kst"]
    horizon_sets = (
        frame.groupby(group_cols, dropna=False)["horizon_hours"]
        .apply(lambda s: frozenset(int(x) for x in s))
        .reset_index(name="horizon_set")
    )
    complete = horizon_sets[horizon_sets["horizon_set"] == horizons][group_cols]
    return frame.merge(complete, on=group_cols, how="inner")


class ImageDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, image_cache: dict[str, np.ndarray], num_cols: list[str]):
        self.num = frame[num_cols].to_numpy(dtype=np.float32)
        self.region = frame["region_id"].to_numpy(dtype=np.int64)
        self.horizon = frame["horizon_id"].to_numpy(dtype=np.int64)
        self.y = frame["target_capacity_factor"].to_numpy(dtype=np.float32)
        self.image_files = sorted(frame["image_file"].unique().tolist())
        self.file_to_id = {file_name: idx for idx, file_name in enumerate(self.image_files)}
        self.file_id = frame["image_file"].map(self.file_to_id).to_numpy(dtype=np.int64)
        self.image_row = frame["image_row"].to_numpy(dtype=np.int64)
        self.images = [image_cache[file_name] for file_name in self.image_files]

    def __len__(self) -> int:
        return len(self.y)

    def __getitem__(self, idx: int):
        image = self.images[self.file_id[idx]][self.image_row[idx]]
        image = image.reshape(12, image.shape[-2], image.shape[-1])
        return (
            torch.from_numpy(image),
            torch.from_numpy(self.num[idx]),
            torch.tensor(self.region[idx], dtype=torch.long),
            torch.tensor(self.horizon[idx], dtype=torch.long),
            torch.tensor(self.y[idx], dtype=torch.float32),
        )


class ConvBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, drop: float = 0.05):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.SiLU(),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.SiLU(),
            nn.Dropout2d(drop),
        )

    def forward(self, x):
        return self.net(x)


class ImageNet(nn.Module):
    def __init__(self, num_dim: int, n_regions: int, n_horizons: int):
        super().__init__()
        scale = torch.tensor([100.0, 100.0, 9.0, 3.0] * 3).view(1, 12, 1, 1)
        self.register_buffer("scale", scale)
        self.region_emb = nn.Embedding(n_regions, 8)
        self.horizon_emb = nn.Embedding(n_horizons, 4)
        self.image = nn.Sequential(
            ConvBlock(12, 32, drop=0.05),
            nn.MaxPool2d(2),
            ConvBlock(32, 64, drop=0.07),
            nn.MaxPool2d(2),
            ConvBlock(64, 128, drop=0.10),
            nn.MaxPool2d(2),
            ConvBlock(128, 128, drop=0.10),
            nn.AdaptiveAvgPool2d(1),
        )
        self.tab = nn.Sequential(
            nn.Linear(num_dim + 8 + 4, 128),
            nn.LayerNorm(128),
            nn.SiLU(),
            nn.Dropout(0.10),
            nn.Linear(128, 128),
            nn.SiLU(),
        )
        self.head = nn.Sequential(
            nn.Linear(128 + 128, 128),
            nn.SiLU(),
            nn.Dropout(0.20),
            nn.Linear(128, 64),
            nn.SiLU(),
            nn.Linear(64, 1),
        )

    def normalize_image(self, image):
        image = image.float()
        image = torch.where(image == 255.0, torch.zeros_like(image), image)
        return image / self.scale

    def forward(self, image, num, region, horizon):
        image = self.normalize_image(image)
        image_feat = self.image(image).flatten(1)
        tab_feat = self.tab(torch.cat([num, self.region_emb(region), self.horizon_emb(horizon)], dim=1))
        return 1.2 * torch.sigmoid(self.head(torch.cat([image_feat, tab_feat], dim=1)).squeeze(1))


def load_images(data_dir: Path, frame: pd.DataFrame) -> dict[str, np.ndarray]:
    image_files = sorted(frame["image_file"].dropna().unique().tolist())
    return {file_name: np.load(data_dir / "images" / file_name)["images"] for file_name in image_files}


def evaluate(
    model: nn.Module,
    frame: pd.DataFrame,
    image_cache: dict[str, np.ndarray],
    *,
    num_cols: list[str],
    device: str,
    batch_size: int,
    num_workers: int,
) -> pd.DataFrame:
    kwargs = {
        "dataset": ImageDataset(frame, image_cache, num_cols),
        "batch_size": batch_size,
        "shuffle": False,
        "num_workers": num_workers,
        "pin_memory": device == "cuda",
    }
    if num_workers > 0:
        kwargs["persistent_workers"] = True
        kwargs["prefetch_factor"] = 2
    loader = DataLoader(**kwargs)

    preds_all = []
    y_all = []
    model.eval()
    with torch.no_grad():
        for image, num, region, horizon, y in loader:
            image = image.to(device, non_blocking=True)
            num = num.to(device, non_blocking=True)
            region = region.to(device, non_blocking=True)
            horizon = horizon.to(device, non_blocking=True)
            with torch.amp.autocast(
                device_type="cuda",
                dtype=torch.bfloat16,
                enabled=device == "cuda",
            ):
                pred = model(image, num, region, horizon)
            preds_all.append(pred.detach().float().cpu())
            y_all.append(y.detach().float().cpu())

    out = frame[[
        "target_timestamp_kst",
        "region",
        "horizon_hours",
        "hour",
        "solar_elevation",
        "target_capacity_factor",
    ]].copy()
    out["pred"] = np.clip(torch.cat(preds_all).numpy(), 0, 1.2)
    out["true"] = torch.cat(y_all).numpy()
    out["abs_error"] = np.abs(out["pred"] - out["target_capacity_factor"])
    out["sq_error"] = (out["pred"] - out["target_capacity_factor"]) ** 2
    return out


def metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    return {
        "rows": int(len(frame)),
        "mae": float(frame["abs_error"].mean()),
        "rmse": float(np.sqrt(frame["sq_error"].mean())),
    }


def group_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for group_name, column in [("horizon", "horizon_hours"), ("region", "region"), ("hour", "hour")]:
        for key, group in frame.groupby(column, dropna=False):
            row = {"group": group_name, "key": key}
            row.update(metrics(group))
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = args.device

    checkpoint = torch.load(args.checkpoint, map_location=device, weights_only=False)
    num_cols = checkpoint.get("num_cols", DEFAULT_NUM_COLS)
    region_map = checkpoint["region_map"]
    horizon_map = normalize_horizon_map(checkpoint["horizon_map"])

    val_path = args.data_dir / "metadata" / f"samples_daylight_{args.variant}_val.parquet"
    raw_val = pd.read_parquet(val_path)
    val = prepare_frame(raw_val, region_map=region_map, horizon_map=horizon_map)
    fair_val = fair_horizon_rows(val)
    image_cache = load_images(args.data_dir, val)

    model = ImageNet(
        num_dim=len(num_cols),
        n_regions=len(region_map),
        n_horizons=len(horizon_map),
    ).to(device)
    model.load_state_dict(checkpoint["model_state"])

    all_pred = evaluate(
        model,
        val,
        image_cache,
        num_cols=num_cols,
        device=device,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )
    fair_pred = evaluate(
        model,
        fair_val,
        image_cache,
        num_cols=num_cols,
        device=device,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
    )

    all_pred.to_csv(args.output_dir / f"{args.variant}_val_predictions.csv", index=False)
    fair_pred.to_csv(args.output_dir / f"{args.variant}_fair_val_predictions.csv", index=False)
    group_metrics(all_pred).to_csv(args.output_dir / f"{args.variant}_group_metrics.csv", index=False)
    group_metrics(fair_pred).to_csv(args.output_dir / f"{args.variant}_fair_group_metrics.csv", index=False)

    summary = {
        "variant": args.variant,
        "checkpoint": str(args.checkpoint),
        "data_dir": str(args.data_dir),
        "all_val": metrics(all_pred),
        "fair_val": metrics(fair_pred),
    }
    (args.output_dir / f"{args.variant}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
