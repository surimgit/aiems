from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from runpod.handler import handler


DEFAULT_MODEL_PATH = Path("ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib")
DEFAULT_VAL_PATH = Path("ems/ai/data/processed/kpx_5min_capacity_factor/kpx_5min_capacity_factor_val.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RunPod capacity-factor predict handler locally.")
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--val-path", default=str(DEFAULT_VAL_PATH))
    parser.add_argument("--output-path", default="ems/ai/outputs/runpod_capacity_factor_smoke_result.json")
    parser.add_argument("--rows", type=int, default=24)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_path = Path(args.model_path)
    val_path = Path(args.val_path)
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not val_path.exists():
        raise FileNotFoundError(f"Validation CSV not found: {val_path}")

    frame = pd.read_csv(val_path).head(args.rows).copy()
    frame["target_time"] = pd.to_datetime(frame["timestamp"]) + pd.Timedelta(hours=1)
    frame["target_time"] = frame["target_time"].dt.strftime("%Y-%m-%dT%H:%M:%S+09:00")
    frame["installed_capacity_kw"] = frame["estimated_capacity_wh"] / 1000.0

    payload = {
        "task": "predict_capacity_factor",
        "model_path": str(model_path),
        "model_version": model_path.parent.name,
        "features": frame.to_dict(orient="records"),
    }
    result = handler({"input": payload})

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
