from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from runpod.handler import handler


DEFAULT_DATA_ROOT = Path(r"G:\내 드라이브\s305-ai-data")
DEFAULT_MODEL_PATH = Path("ems/ai/models/solar_kpx_lightgbm/model.joblib")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RunPod predict handler locally with postprocess fields.")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT))
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--val-path", default=None)
    parser.add_argument("--output-path", default="ems/ai/outputs/runpod_predict_smoke_result.json")
    parser.add_argument("--rows", type=int, default=24)
    parser.add_argument("--installed-capacity-kw", type=float, default=1_000_000.0)
    parser.add_argument("--latitude", type=float, default=34.8118)
    parser.add_argument("--longitude", type=float, default=126.3922)
    parser.add_argument("--timezone", default="Asia/Seoul")
    return parser.parse_args()


def estimated_irradiance(row: pd.Series, is_daylight: int) -> float:
    if not is_daylight:
        return 0.0
    try:
        value = float(row.get("irradiance", 0.0))
    except (TypeError, ValueError):
        return 0.0
    if 0.0 <= value <= 1.5:
        value *= 1000.0
    return max(value, 0.0)


def build_payload(
    frame: pd.DataFrame,
    model_path: Path,
    rows: int,
    installed_capacity_kw: float,
    latitude: float,
    longitude: float,
    timezone: str,
) -> dict:
    sample = frame.head(rows).copy()
    sample["timestamp"] = pd.to_datetime(sample["timestamp"])
    features = []
    for _, row in sample.iterrows():
        target_timestamp = row["timestamp"] + pd.Timedelta(hours=1)
        hour = int(target_timestamp.hour)
        feature = row.to_dict()
        feature["target_time"] = target_timestamp.isoformat()
        feature["target_hour"] = hour
        feature["latitude"] = latitude
        feature["longitude"] = longitude
        feature["timezone"] = timezone
        feature["installed_capacity_kw"] = installed_capacity_kw
        features.append(feature)

    return {
        "task": "predict",
        "site_id": "PLANT-ALPHA",
        "model_path": str(model_path),
        "model_version": model_path.parent.name,
        "installed_capacity_kw": installed_capacity_kw,
        "features": features,
    }


def main() -> None:
    args = parse_args()
    data_root = Path(args.data_root)
    val_path = Path(args.val_path) if args.val_path else data_root / "processed" / "splits" / "solar_kpx_val.csv"
    model_path = Path(args.model_path)

    if not val_path.exists():
        raise FileNotFoundError(f"Validation CSV not found: {val_path}")
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    frame = pd.read_csv(val_path)
    payload = build_payload(
        frame,
        model_path,
        rows=args.rows,
        installed_capacity_kw=args.installed_capacity_kw,
        latitude=args.latitude,
        longitude=args.longitude,
        timezone=args.timezone,
    )
    result = handler({"input": payload})

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
