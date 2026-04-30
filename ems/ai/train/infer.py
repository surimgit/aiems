from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import torch

from train.config import load_config
from train.dataset import load_dataframe
from train.metrics import mae, mape, masked_mape, rmse
from train.model import BaselineMLP
from train.solar_postprocess import postprocess_solar_predictions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch inference with a trained EMS AI model.")
    parser.add_argument("--config", default="ems/ai/configs/solar_kpx_baseline.yaml")
    parser.add_argument("--input-path", default=None)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--include-target-metrics", action="store_true")
    return parser.parse_args()


def resolve_checkpoint(config: dict, checkpoint_path: str | None) -> Path:
    if checkpoint_path:
        return Path(checkpoint_path)
    return Path(config["output"]["checkpoint_dir"]) / config["output"]["run_name"] / "best.pt"


def resolve_output_path(config: dict, output_path: str | None) -> Path:
    if output_path:
        return Path(output_path)
    return Path("ems/ai/outputs") / f"{config['output']['run_name']}_predictions.csv"


def load_model(config: dict, checkpoint_path: Path, device: torch.device) -> BaselineMLP:
    feature_columns = config["data"]["feature_columns"]
    model = BaselineMLP(
        input_dim=len(feature_columns),
        hidden_dims=config["model"]["hidden_dims"],
        dropout=config["model"]["dropout"],
    ).to(device)

    checkpoint = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    input_path = args.input_path or config["data"]["val_path"]
    checkpoint_path = resolve_checkpoint(config, args.checkpoint)
    output_path = resolve_output_path(config, args.output_path)

    feature_columns = config["data"]["feature_columns"]
    target_column = config["data"]["target_column"]
    frame = load_dataframe(input_path, config["data"]["file_format"])

    missing = [column for column in feature_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing feature columns in input data: {missing}")

    device = torch.device("cuda:0" if config["device"] == "cuda" and torch.cuda.is_available() else "cpu")
    model = load_model(config, checkpoint_path, device)

    features = torch.tensor(frame[feature_columns].to_numpy(), dtype=torch.float32, device=device)
    with torch.no_grad():
        predictions = model(features).detach().cpu().view(-1)
        clipped_predictions = torch.clamp(predictions, min=0.0)

    postprocessed = postprocess_solar_predictions(frame, predictions.numpy())
    result = frame.copy()
    result["raw_predicted_solar_P_kw"] = predictions.numpy()
    result["predicted_solar_P_kw"] = postprocessed["predicted_solar_kw"]
    result["predicted_solar_P_kw_clipped"] = clipped_predictions.numpy()
    result["postprocess_reason"] = postprocessed["postprocess_reason"]

    metrics = None
    if args.include_target_metrics and target_column in frame.columns:
        targets = torch.tensor(frame[target_column].to_numpy(), dtype=torch.float32).view(-1)
        metrics = {
            "mae": mae(predictions, targets),
            "rmse": rmse(predictions, targets),
            "mape": mape(predictions, targets),
            "masked_mape_target_gte_1": masked_mape(predictions, targets, minimum_target=1.0),
            "clipped_mae": mae(clipped_predictions, targets),
            "clipped_rmse": rmse(clipped_predictions, targets),
            "clipped_masked_mape_target_gte_1": masked_mape(
                clipped_predictions,
                targets,
                minimum_target=1.0,
            ),
            "postprocessed_mae": mae(
                torch.tensor(postprocessed["predicted_solar_kw"].to_numpy(), dtype=torch.float32),
                targets,
            ),
            "postprocessed_rmse": rmse(
                torch.tensor(postprocessed["predicted_solar_kw"].to_numpy(), dtype=torch.float32),
                targets,
            ),
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    payload = {
        "input_path": str(input_path),
        "checkpoint_path": str(checkpoint_path),
        "output_path": str(output_path),
        "rows": len(result),
        "metrics": metrics,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
