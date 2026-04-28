from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error

from train.config import load_config
from train.dataset import load_dataframe
from train.solar_postprocess import postprocess_solar_predictions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a LightGBM solar baseline model.")
    parser.add_argument("--config", default="ems/ai/configs/solar_kpx_lightgbm_gpu.yaml")
    return parser.parse_args()


def require_lightgbm():
    try:
        from lightgbm import LGBMRegressor, early_stopping, log_evaluation
    except ImportError as error:
        raise RuntimeError("LightGBM is not installed. Run: pip install -r ems/ai/requirements-train.txt") from error
    return LGBMRegressor, early_stopping, log_evaluation


def build_xy(frame: pd.DataFrame, feature_columns: list[str], target_column: str):
    missing = [column for column in feature_columns + [target_column] if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")
    clean = frame[feature_columns + [target_column]].replace([np.inf, -np.inf], np.nan).dropna()
    return clean[feature_columns], clean[target_column], len(frame), len(clean)


def masked_mape(y_true, y_pred, minimum_target: float = 1.0) -> float | None:
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    mask = np.abs(y_true) >= minimum_target
    if not np.any(mask):
        return None
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100.0)


def compute_metrics(y_true, y_pred) -> dict:
    clipped = np.clip(y_pred, 0.0, None)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "mape": float(mean_absolute_percentage_error(y_true, y_pred) * 100.0),
        "masked_mape_target_gte_1": masked_mape(y_true, y_pred, minimum_target=1.0),
        "clipped_mae": float(mean_absolute_error(y_true, clipped)),
        "clipped_rmse": float(mean_squared_error(y_true, clipped) ** 0.5),
        "clipped_masked_mape_target_gte_1": masked_mape(y_true, clipped, minimum_target=1.0),
    }


def compute_postprocessed_metrics(y_true, postprocessed_pred) -> dict:
    return {
        "postprocessed_mae": float(mean_absolute_error(y_true, postprocessed_pred)),
        "postprocessed_rmse": float(mean_squared_error(y_true, postprocessed_pred) ** 0.5),
        "postprocessed_masked_mape_target_gte_1": masked_mape(
            y_true,
            postprocessed_pred,
            minimum_target=1.0,
        ),
    }


def model_params(config: dict) -> dict:
    params = dict(config["model"])
    params.pop("early_stopping_rounds", None)
    return params


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    LGBMRegressor, early_stopping, log_evaluation = require_lightgbm()

    feature_columns = config["data"]["feature_columns"]
    target_column = config["data"]["target_column"]
    file_format = config["data"]["file_format"]
    train_frame = load_dataframe(config["data"]["train_path"], file_format)
    val_frame = load_dataframe(config["data"]["val_path"], file_format)

    x_train, y_train, train_rows_before, train_rows_after = build_xy(train_frame, feature_columns, target_column)
    x_val, y_val, val_rows_before, val_rows_after = build_xy(val_frame, feature_columns, target_column)

    model = LGBMRegressor(**model_params(config))
    callbacks = [
        early_stopping(config["model"].get("early_stopping_rounds", 50)),
        log_evaluation(period=50),
    ]
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_val, y_val)],
        eval_metric="rmse",
        callbacks=callbacks,
    )

    val_pred = model.predict(x_val)
    metrics = compute_metrics(y_val, val_pred)
    postprocessed = postprocess_solar_predictions(val_frame.loc[x_val.index], val_pred)
    metrics.update(compute_postprocessed_metrics(y_val, postprocessed["predicted_solar_kw"]))

    artifact_dir = Path(config["output"]["artifact_dir"]) / config["output"]["run_name"]
    log_dir = Path(config["output"]["log_dir"]) / config["output"]["run_name"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    model_path = artifact_dir / "model.joblib"
    joblib.dump(
        {
            "model": model,
            "feature_columns": feature_columns,
            "target_column": target_column,
            "config": config,
        },
        model_path,
    )

    predictions = val_frame.loc[x_val.index].copy()
    predictions["raw_predicted_solar_P_kw"] = val_pred
    predictions["predicted_solar_P_kw"] = postprocessed["predicted_solar_kw"]
    predictions["predicted_solar_P_kw_clipped"] = np.clip(val_pred, 0.0, None)
    predictions["postprocess_reason"] = postprocessed["postprocess_reason"]
    predictions.to_csv(artifact_dir / "validation_predictions.csv", index=False)

    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)
    importance.to_csv(artifact_dir / "feature_importance.csv", index=False)

    payload = {
        "run_name": config["output"]["run_name"],
        "model_path": str(model_path),
        "train_rows_before_dropna": train_rows_before,
        "train_rows_after_dropna": train_rows_after,
        "val_rows_before_dropna": val_rows_before,
        "val_rows_after_dropna": val_rows_after,
        "metrics": metrics,
    }
    (artifact_dir / "metrics.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    (log_dir / "metrics.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
