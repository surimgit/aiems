from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from train.solar_postprocess import postprocess_solar_predictions


DEFAULT_DATA_ROOT = Path(r"G:\내 드라이브\s305-ai-data")
DEFAULT_MODEL_PATH = Path("ems/ai/models/solar_kpx_lightgbm/model.joblib")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the solar LightGBM model against simple baselines.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--val-path", default=None)
    parser.add_argument("--output-path", default="ems/ai/outputs/solar_model_validation_report.json")
    parser.add_argument("--daylight-target-threshold-kw", type=float, default=1000.0)
    parser.add_argument("--daylight-source", choices=["hour", "solar-location"], default="solar-location")
    parser.add_argument("--latitude", type=float, default=34.8118)
    parser.add_argument("--longitude", type=float, default=126.3922)
    parser.add_argument("--timezone", default="Asia/Seoul")
    parser.add_argument("--include-estimated-irradiance", action="store_true")
    return parser.parse_args()


def metric_payload(y_true: pd.Series, y_pred: pd.Series) -> dict[str, float | int | None]:
    mask = y_true.notna() & y_pred.notna()
    if not mask.any():
        return {"rows": 0, "mae": None, "rmse": None}
    true = y_true[mask].astype(float)
    pred = y_pred[mask].astype(float)
    return {
        "rows": int(mask.sum()),
        "mae": float(mean_absolute_error(true, pred)),
        "rmse": float(mean_squared_error(true, pred) ** 0.5),
    }


def summarize_frame(frame: pd.DataFrame) -> dict[str, Any]:
    timestamp = pd.to_datetime(frame["timestamp"])
    expected_hours = int(((timestamp.max() - timestamp.min()).total_seconds() / 3600) + 1)
    return {
        "rows": int(len(frame)),
        "range_start": str(timestamp.min()),
        "range_end": str(timestamp.max()),
        "expected_hourly_rows": expected_hours,
        "missing_hourly_rows": int(max(expected_hours - len(frame), 0)),
        "duplicate_timestamps": int(timestamp.duplicated().sum()),
        "null_cells": int(frame.isna().sum().sum()),
    }


def load_model(model_path: Path) -> tuple[Any, list[str], str]:
    artifact = joblib.load(model_path)
    model = artifact["model"] if isinstance(artifact, dict) and "model" in artifact else artifact
    feature_columns = artifact.get("feature_columns") if isinstance(artifact, dict) else None
    target_column = artifact.get("target_column") if isinstance(artifact, dict) else "future_solar_P_kw"
    if not feature_columns:
        raise ValueError("Model artifact does not include feature_columns.")
    return model, list(feature_columns), target_column


def add_prediction_columns(
    frame: pd.DataFrame,
    model: Any,
    feature_columns: list[str],
    include_estimated_irradiance: bool,
    daylight_source: str,
    latitude: float,
    longitude: float,
    timezone: str,
) -> pd.DataFrame:
    missing = [column for column in feature_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Validation data is missing feature columns: {missing}")

    result = frame.copy()
    timestamp = pd.to_datetime(result["timestamp"])
    target_timestamp = timestamp + pd.Timedelta(hours=1)
    result["target_time"] = target_timestamp.dt.strftime("%Y-%m-%dT%H:%M:%S")
    result["target_hour"] = target_timestamp.dt.hour
    if daylight_source == "hour":
        result["is_daylight"] = result["target_hour"].between(6, 19).astype(int)
    else:
        result["latitude"] = latitude
        result["longitude"] = longitude
        result["timezone"] = timezone
    if include_estimated_irradiance:
        result["estimated_irradiance"] = result.apply(estimated_irradiance, axis=1)
    raw_predictions = model.predict(result[feature_columns])
    postprocessed = postprocess_solar_predictions(result, raw_predictions)
    result["model_raw_pred_kw"] = raw_predictions
    result["model_pred_kw"] = postprocessed["predicted_solar_kw"]
    result["model_postprocess_reason"] = postprocessed["postprocess_reason"]
    result["baseline_prev_hour_kw"] = result["past_solar_P_kw"]
    result["baseline_yesterday_kw"] = result["past_solar_P_kw_lag_24"]
    return result


def estimated_irradiance(row: pd.Series) -> float:
    if int(row["is_daylight"]) <= 0:
        return 0.0
    try:
        value = float(row.get("irradiance", 0.0))
    except (TypeError, ValueError):
        return 0.0
    if 0.0 <= value <= 1.5:
        value *= 1000.0
    return max(value, 0.0)


def compare_metrics(frame: pd.DataFrame, target_column: str) -> dict[str, Any]:
    predictors = {
        "model": "model_pred_kw",
        "baseline_prev_hour": "baseline_prev_hour_kw",
        "baseline_yesterday_same_hour": "baseline_yesterday_kw",
    }
    return {
        name: metric_payload(frame[target_column], frame[column])
        for name, column in predictors.items()
    }


def grouped_metrics(frame: pd.DataFrame, target_column: str, key: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for value, group in frame.groupby(key):
        payload[str(value)] = compare_metrics(group, target_column)
    return payload


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root)
    val_path = Path(args.val_path) if args.val_path else data_root / "processed" / "splits" / "solar_kpx_val.csv"
    model_path = Path(args.model_path)
    output_path = Path(args.output_path)

    if not val_path.exists():
        raise FileNotFoundError(f"Validation CSV not found: {val_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    frame = pd.read_csv(val_path)
    model, feature_columns, target_column = load_model(model_path)
    if target_column not in frame.columns:
        raise ValueError(f"Validation data is missing target column: {target_column}")

    result = add_prediction_columns(
        frame,
        model,
        feature_columns,
        include_estimated_irradiance=args.include_estimated_irradiance,
        daylight_source=args.daylight_source,
        latitude=args.latitude,
        longitude=args.longitude,
        timezone=args.timezone,
    )
    result["timestamp"] = pd.to_datetime(result["timestamp"])
    result["month"] = result["timestamp"].dt.strftime("%Y-%m")
    result["hour"] = result["timestamp"].dt.hour
    result["is_daylight_target"] = result[target_column].astype(float) >= args.daylight_target_threshold_kw

    daylight = result[result["is_daylight_target"]]
    night_or_low = result[~result["is_daylight_target"]]

    report = {
        "data_root": str(data_root),
        "val_path": str(val_path),
        "model_path": str(model_path),
        "target_column": target_column,
        "feature_columns": feature_columns,
        "include_estimated_irradiance": args.include_estimated_irradiance,
        "daylight_source": args.daylight_source,
        "latitude": args.latitude,
        "longitude": args.longitude,
        "timezone": args.timezone,
        "data_summary": summarize_frame(result),
        "overall": compare_metrics(result, target_column),
        "daylight_target": compare_metrics(daylight, target_column),
        "night_or_low_target": compare_metrics(night_or_low, target_column),
        "by_month": grouped_metrics(result, target_column, "month"),
        "by_hour": grouped_metrics(result, target_column, "hour"),
        "postprocess_reasons": result["model_postprocess_reason"].value_counts().to_dict(),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
