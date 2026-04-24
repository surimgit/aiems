from __future__ import annotations

import argparse
import random

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader

from train.checkpoint import load_latest_checkpoint, save_checkpoint
from train.config import load_config
from train.dataset import TabularDataset, load_dataframe
from train.logger import append_metrics, create_logger
from train.metrics import mae, mape, rmse
from train.model import BaselineMLP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a baseline EMS AI model.")
    parser.add_argument("--config", default="ems/ai/configs/baseline.yaml")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def resolve_device(device_name: str) -> torch.device:
    if device_name == "cuda" and torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def build_loader(frame, feature_columns, target_column, batch_size, num_workers, shuffle):
    dataset = TabularDataset(frame, feature_columns, target_column)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=num_workers)


def run_epoch(model, loader, criterion, device, optimizer=None):
    training = optimizer is not None
    model.train() if training else model.eval()

    total_loss = 0.0
    predictions_list = []
    targets_list = []

    for features, targets in loader:
        features = features.to(device)
        targets = targets.to(device)

        if training:
            optimizer.zero_grad()

        with torch.set_grad_enabled(training):
            predictions = model(features)
            loss = criterion(predictions, targets)
            if training:
                loss.backward()
                optimizer.step()

        total_loss += loss.item() * features.size(0)
        predictions_list.append(predictions.detach().cpu())
        targets_list.append(targets.detach().cpu())

    predictions = torch.cat(predictions_list)
    targets = torch.cat(targets_list)
    size = len(loader.dataset)

    return {
        "loss": total_loss / size,
        "mae": mae(predictions, targets),
        "rmse": rmse(predictions, targets),
        "mape": mape(predictions, targets),
    }


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    set_seed(config["seed"])

    feature_columns = config["data"]["feature_columns"]
    target_column = config["data"]["target_column"]
    file_format = config["data"]["file_format"]

    train_frame = load_dataframe(config["data"]["train_path"], file_format)
    val_frame = load_dataframe(config["data"]["val_path"], file_format)

    train_loader = build_loader(
        train_frame,
        feature_columns,
        target_column,
        config["training"]["batch_size"],
        config["training"]["num_workers"],
        True,
    )
    val_loader = build_loader(
        val_frame,
        feature_columns,
        target_column,
        config["training"]["batch_size"],
        config["training"]["num_workers"],
        False,
    )

    device = resolve_device(config["device"])
    model = BaselineMLP(
        input_dim=len(feature_columns),
        hidden_dims=config["model"]["hidden_dims"],
        dropout=config["model"]["dropout"],
    ).to(device)

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=config["training"]["learning_rate"],
        weight_decay=config["training"]["weight_decay"],
    )
    criterion = nn.MSELoss()

    run_name = config["output"]["run_name"]
    checkpoint_dir = config["output"]["checkpoint_dir"]
    log_dir = config["output"]["log_dir"]
    logger = create_logger(log_dir, run_name)

    start_epoch = 1
    best_val_rmse = float("inf")

    if args.resume:
        checkpoint = load_latest_checkpoint(checkpoint_dir, run_name)
        if checkpoint:
            model.load_state_dict(checkpoint["model_state_dict"])
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            start_epoch = checkpoint["epoch"] + 1
            best_val_rmse = checkpoint["metrics"].get("val_rmse", best_val_rmse)
            logger.info("Resumed from epoch %s", checkpoint["epoch"])

    for epoch in range(start_epoch, config["training"]["epochs"] + 1):
        train_metrics = run_epoch(model, train_loader, criterion, device, optimizer)
        val_metrics = run_epoch(model, val_loader, criterion, device)

        payload = {
            "epoch": epoch,
            "train_loss": train_metrics["loss"],
            "train_mae": train_metrics["mae"],
            "train_rmse": train_metrics["rmse"],
            "train_mape": train_metrics["mape"],
            "val_loss": val_metrics["loss"],
            "val_mae": val_metrics["mae"],
            "val_rmse": val_metrics["rmse"],
            "val_mape": val_metrics["mape"],
        }

        logger.info(
            "epoch=%s train_loss=%.6f val_loss=%.6f val_rmse=%.6f",
            epoch,
            payload["train_loss"],
            payload["val_loss"],
            payload["val_rmse"],
        )
        append_metrics(log_dir, run_name, payload)

        is_best = payload["val_rmse"] < best_val_rmse
        if is_best:
            best_val_rmse = payload["val_rmse"]

        save_checkpoint(checkpoint_dir, run_name, epoch, model, optimizer, payload, is_best)


if __name__ == "__main__":
    main()
