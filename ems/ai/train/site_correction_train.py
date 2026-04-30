from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from train.config import load_config
from train.dataset import load_dataframe
from train.lightgbm_train import require_lightgbm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a site correction model from prediction-vs-actual logs.")
    parser.add_argument("--config", default="ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml")
    return parser.parse_args()


def add_time_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    time_column = "timestamp_utc" if "timestamp_utc" in output.columns else "target_time"
    if time_column in output.columns:
        ts = pd.to_datetime(output[time_column], utc=True)
        output["hour_of_day_sin"] = np.sin(2 * np.pi * ts.dt.hour / 24.0)
        output["hour_of_day_cos"] = np.cos(2 * np.pi * ts.dt.hour / 24.0)
        output["day_of_year_sin"] = np.sin(2 * np.pi * ts.dt.dayofyear / 366.0)
        output["day_of_year_cos"] = np.cos(2 * np.pi * ts.dt.dayofyear / 366.0)
    return output


def prepare_frame(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    baseline = config["data"]["baseline_column"]
    actual = config["data"]["actual_column"]
    target = config["data"]["target_column"]
    min_baseline = float(config["target"].get("min_baseline_kw", 1.0))
    min_ratio = float(config["target"].get("min_ratio", 0.0))
    max_ratio = float(config["target"].get("max_ratio", 2.0))

    output = add_time_features(frame)
    missing = [column for column in [baseline, actual] if column not in output.columns]
    if missing:
        raise ValueError(
            "Site correction requires prediction-vs-actual data. "
            f"Missing columns: {missing}"
        )
    output = output[pd.to_numeric(output[baseline], errors="coerce") >= min_baseline].copy()
    output[target] = pd.to_numeric(output[actual], errors="coerce") / pd.to_numeric(output[baseline], errors="coerce")
    output[target] = output[target].clip(lower=min_ratio, upper=max_ratio)
    return output


def build_xy(frame: pd.DataFrame, config: dict):
    feature_columns = config["data"]["feature_columns"]
    target_column = config["data"]["target_column"]
    missing = [column for column in feature_columns + [target_column] if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing columns in correction dataset: {missing}")
    clean = frame[feature_columns + [target_column]].replace([np.inf, -np.inf], np.nan).dropna()
    return clean[feature_columns], clean[target_column], len(frame), len(clean)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    LGBMRegressor, early_stopping, log_evaluation = require_lightgbm()

    train_frame = prepare_frame(load_dataframe(config["data"]["train_path"], config["data"]["file_format"]), config)
    val_frame = prepare_frame(load_dataframe(config["data"]["val_path"], config["data"]["file_format"]), config)
    x_train, y_train, train_rows_before, train_rows_after = build_xy(train_frame, config)
    x_val, y_val, val_rows_before, val_rows_after = build_xy(val_frame, config)

    model_params = dict(config["model"])
    early_stopping_rounds = model_params.pop("early_stopping_rounds", 50)
    model = LGBMRegressor(**model_params)
    model.fit(
        x_train,
        y_train,
        eval_set=[(x_val, y_val)],
        eval_metric="rmse",
        callbacks=[early_stopping(early_stopping_rounds), log_evaluation(period=50)],
    )

    ratio_pred = np.clip(model.predict(x_val), config["target"]["min_ratio"], config["target"]["max_ratio"])
    baseline_col = config["data"]["baseline_column"]
    actual_col = config["data"]["actual_column"]
    aligned_val = val_frame.loc[x_val.index].copy()
    corrected_kw = pd.to_numeric(aligned_val[baseline_col], errors="coerce").to_numpy() * ratio_pred
    actual_kw = pd.to_numeric(aligned_val[actual_col], errors="coerce").to_numpy()

    metrics = {
        "ratio_mae": float(mean_absolute_error(y_val, ratio_pred)),
        "ratio_rmse": float(mean_squared_error(y_val, ratio_pred) ** 0.5),
        "corrected_kw_mae": float(mean_absolute_error(actual_kw, corrected_kw)),
        "corrected_kw_rmse": float(mean_squared_error(actual_kw, corrected_kw) ** 0.5),
    }

    artifact_dir = Path(config["output"]["artifact_dir"]) / config["output"]["run_name"]
    log_dir = Path(config["output"]["log_dir"]) / config["output"]["run_name"]
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    model_path = artifact_dir / "model.joblib"
    joblib.dump(
        {
            "model": model,
            "feature_columns": config["data"]["feature_columns"],
            "target_column": config["data"]["target_column"],
            "config": config,
        },
        model_path,
    )

    aligned_val["predicted_correction_ratio"] = ratio_pred
    aligned_val["predicted_solar_kw_corrected"] = corrected_kw
    aligned_val.to_csv(artifact_dir / "validation_predictions.csv", index=False)

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
