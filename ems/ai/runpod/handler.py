from __future__ import annotations

import base64
import importlib
import importlib.metadata
import json
import os
import shutil
import subprocess
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

try:
    from ems.ai.train.solar_postprocess import postprocess_solar_predictions
except ImportError:
    from train.solar_postprocess import postprocess_solar_predictions

try:
    import runpod
except ImportError:
    runpod = None


WORKSPACE = Path(os.getenv("S305_RUNPOD_WORKSPACE", "/workspace"))
DEFAULT_DATA_ROOT = WORKSPACE / "s305-ai-data"
DEFAULT_OUTPUT_ROOT = WORKSPACE / "runs"
DEFAULT_CAPACITY_FACTOR_MODEL = "/app/ems/ai/models/kpx_5min_capacity_factor_lightgbm/model.joblib"
DEFAULT_SATELLITE_MODEL = "/app/ems/ai/checkpoints/satellite_wind_safe_multihorizon_24h_v10/best_model.pt"


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        with destination.open("wb") as file:
            shutil.copyfileobj(response, file)


def _safe_member_path(member_name: str) -> Path:
    normalized = member_name.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe zip member path: {member_name}")
    return path


def _extract_zip(zip_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            relative_path = _safe_member_path(member.filename)
            target_path = destination / relative_path
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target_path.open("wb") as target:
                shutil.copyfileobj(source, target)


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_dir.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir))


def _upload(url: str, file_path: Path) -> None:
    with file_path.open("rb") as file:
        request = urllib.request.Request(url, data=file.read(), method="PUT")
        request.add_header("Content-Type", "application/zip")
        with urllib.request.urlopen(request, timeout=120) as response:
            if response.status >= 400:
                raise RuntimeError(f"Upload failed with status {response.status}")


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _run_command(command: list[str], env: dict[str, str], cwd: Path) -> dict[str, Any]:
    started_at = time.time()
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "command": " ".join(command),
        "returncode": completed.returncode,
        "seconds": round(time.time() - started_at, 3),
        "log_tail": completed.stdout[-6000:],
    }


def _stage_commands(stages: list[str]) -> list[tuple[str, list[str]]]:
    available = {
        "mlp": ["python", "-m", "train.train", "--config", "ems/ai/configs/solar_kpx_baseline_gpu.yaml"],
        "lightgbm": [
            "python",
            "-m",
            "train.lightgbm_train",
            "--config",
            "ems/ai/configs/solar_kpx_lightgbm_gpu.yaml",
        ],
        "site_correction": [
            "python",
            "-m",
            "train.site_correction_train",
            "--config",
            "ems/ai/configs/solar_site_correction_lightgbm_gpu.yaml",
        ],
    }
    unknown = [stage for stage in stages if stage not in available]
    if unknown:
        raise ValueError(f"Unknown training stages: {unknown}")
    return [(stage, available[stage]) for stage in stages]


def _predict(payload: dict[str, Any]) -> dict[str, Any]:
    model_path = Path(
        payload.get(
            "model_path",
            os.getenv("S305_SOLAR_MODEL_PATH", "/app/ems/ai/models/solar_kpx_lightgbm/model.joblib"),
        )
    )
    if not model_path.exists():
        raise FileNotFoundError(f"Solar model file not found: {model_path}")

    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("input.features must be a non-empty list of feature objects")

    artifact = joblib.load(model_path)
    model = artifact["model"] if isinstance(artifact, dict) and "model" in artifact else artifact
    feature_columns = artifact.get("feature_columns") if isinstance(artifact, dict) else payload.get("feature_columns")
    if not feature_columns:
        raise ValueError("feature_columns are missing from model artifact and request payload")

    frame = pd.DataFrame(features)
    missing = [column for column in feature_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing feature columns for prediction: {missing}")

    raw_predictions = model.predict(frame[feature_columns])
    postprocessed = postprocess_solar_predictions(
        frame,
        raw_predictions,
        installed_capacity_kw=payload.get("installed_capacity_kw"),
        irradiance_threshold=float(payload.get("irradiance_threshold", 10.0)),
    )

    predictions: list[dict[str, Any]] = []
    for index, row in postprocessed.iterrows():
        source = features[index]
        reason = row["postprocess_reason"]
        predictions.append(
            {
                "target_time": source.get("target_time"),
                "site_id": source.get("site_id", payload.get("site_id")),
                "raw_predicted_solar_kw": row["raw_predicted_solar_kw"],
                "predicted_solar_kw": row["predicted_solar_kw"],
                "postprocess_reason": reason,
                "confidence": 0.95 if reason == "night_zero_clamp" else 0.8,
                "fallback_flag": False,
                "model_version": payload.get("model_version", model_path.parent.name),
            }
        )

    return {
        "ok": True,
        "task": "predict",
        "model_path": str(model_path),
        "rows": len(predictions),
        "predictions": predictions,
    }


def _capacity_kw(payload: dict[str, Any], source: dict[str, Any]) -> float:
    value = source.get("installed_capacity_kw", payload.get("installed_capacity_kw"))
    if value is None:
        value = source.get("estimated_capacity_wh", payload.get("estimated_capacity_wh"))
        if value is not None:
            value = float(value) / 1000.0
    if value is None:
        raise ValueError("installed_capacity_kw is required for capacity-factor prediction")
    capacity = float(value)
    if capacity <= 0:
        raise ValueError(f"installed_capacity_kw must be positive: {capacity}")
    return capacity


def _is_night_for_capacity_factor(source: dict[str, Any]) -> bool:
    for name in ("is_daylight", "daylight_flag"):
        value = source.get(name)
        if value is not None and not pd.isna(value):
            return float(value) <= 0.0
    for name in ("solar_elevation_mid", "solar_elevation", "solar_elevation_deg"):
        value = source.get(name)
        if value is not None and not pd.isna(value):
            return float(value) <= 0.0
    return False


def _predict_capacity_factor(payload: dict[str, Any]) -> dict[str, Any]:
    model_path = Path(
        payload.get(
            "model_path",
            os.getenv("S305_CAPACITY_FACTOR_MODEL_PATH", DEFAULT_CAPACITY_FACTOR_MODEL),
        )
    )
    if not model_path.exists():
        raise FileNotFoundError(f"Capacity-factor model file not found: {model_path}")

    features = payload.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("input.features must be a non-empty list of feature objects")

    artifact = joblib.load(model_path)
    model = artifact["model"] if isinstance(artifact, dict) and "model" in artifact else artifact
    feature_columns = artifact.get("feature_columns") if isinstance(artifact, dict) else payload.get("feature_columns")
    if not feature_columns:
        raise ValueError("feature_columns are missing from model artifact and request payload")

    frame = pd.DataFrame(features)
    missing = [column for column in feature_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing feature columns for capacity-factor prediction: {missing}")

    raw_predictions = model.predict(frame[feature_columns])
    clipped_predictions = np.clip(raw_predictions, 0.0, float(payload.get("max_capacity_factor", 1.0)))

    predictions: list[dict[str, Any]] = []
    for index, raw_prediction in enumerate(raw_predictions):
        source = features[index]
        predicted_capacity_factor = float(clipped_predictions[index])
        reasons: list[str] = []

        if _is_night_for_capacity_factor(source):
            predicted_capacity_factor = 0.0
            reasons.append("night_zero_clamp")
        elif raw_prediction < 0.0:
            reasons.append("negative_clamp")
        elif predicted_capacity_factor != float(raw_prediction):
            reasons.append("capacity_factor_clamp")

        installed_capacity_kw = _capacity_kw(payload, source)
        predictions.append(
            {
                "target_time": source.get("target_time"),
                "region": source.get("region", payload.get("region")),
                "site_id": source.get("site_id", payload.get("site_id")),
                "raw_predicted_capacity_factor": float(raw_prediction),
                "predicted_capacity_factor": predicted_capacity_factor,
                "installed_capacity_kw": installed_capacity_kw,
                "predicted_generation_kw": predicted_capacity_factor * installed_capacity_kw,
                "postprocess_reason": ",".join(reasons) if reasons else "none",
                "confidence": 0.95 if "night_zero_clamp" in reasons else 0.8,
                "fallback_flag": False,
                "model_version": payload.get("model_version", model_path.parent.name),
            }
        )

    return {
        "ok": True,
        "task": "predict_capacity_factor",
        "model_path": str(model_path),
        "rows": len(predictions),
        "structured_profile": payload.get("structured_profile"),
        "context_features": payload.get("context_features"),
        "predictions": predictions,
    }


def _predict_satellite_capacity_factor(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from ems.ai.inference.satellite_wind_safe import predict_satellite_capacity_factor
    except ImportError:
        from inference.satellite_wind_safe import predict_satellite_capacity_factor

    model_path = payload.get("model_path") or os.getenv("S305_SATELLITE_MODEL_PATH", DEFAULT_SATELLITE_MODEL)
    return predict_satellite_capacity_factor(
        payload,
        model_path=model_path,
        device=payload.get("device"),
        image_normalization=payload.get("image_normalization"),
    )


def _predict_live_satellite_capacity_factor(payload: dict[str, Any]) -> dict[str, Any]:
    from ems.ai.service.app.services.live_satellite_service import LiveSatellitePredictionService

    class _PredictionServiceAdapter:
        def predict_satellite_capacity_factor(self, prediction_payload: dict[str, Any]) -> dict[str, Any]:
            return _predict_satellite_capacity_factor(prediction_payload)

    class _DisabledRunpodClient:
        @property
        def enabled(self) -> bool:
            return False

    return LiveSatellitePredictionService(
        prediction_service=_PredictionServiceAdapter(),
        runpod_client=_DisabledRunpodClient(),
    ).predict(payload)


def _runtime_check() -> dict[str, Any]:
    modules = ["torch", "numpy", "pandas", "xarray", "pyproj", "netCDF4", "h5netcdf", "requests", "runpod"]
    imports: dict[str, dict[str, Any]] = {}
    for name in modules:
        try:
            importlib.import_module(name)
            try:
                version = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                version = None
            imports[name] = {"ok": True, "version": version}
        except Exception as exc:
            imports[name] = {"ok": False, "error": str(exc)}

    cuda: dict[str, Any] = {"available": False}
    try:
        import torch

        cuda = {
            "available": bool(torch.cuda.is_available()),
            "device_count": int(torch.cuda.device_count()),
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
    except Exception as exc:
        cuda = {"available": False, "error": str(exc)}

    return {
        "ok": all(item["ok"] for item in imports.values()),
        "task": "runtime_check",
        "imports": imports,
        "cuda": cuda,
        "satellite_model_exists": Path(os.getenv("S305_SATELLITE_MODEL_PATH", DEFAULT_SATELLITE_MODEL)).exists(),
    }


def _train(payload: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(payload.get("repo_root", "/app"))
    data_root = Path(payload.get("data_root", DEFAULT_DATA_ROOT))
    output_root = Path(payload.get("output_root", DEFAULT_OUTPUT_ROOT))
    stages = payload.get("stages", ["mlp", "lightgbm", "site_correction"])

    data_zip_url = payload.get("data_zip_url")
    result_upload_url = payload.get("result_upload_url")
    include_artifact_base64 = bool(payload.get("include_artifact_base64", False))

    if data_zip_url:
        archive_path = WORKSPACE / "input" / "training_data.zip"
        _download(data_zip_url, archive_path)
        _extract_zip(archive_path, WORKSPACE)

    if not data_root.exists():
        raise FileNotFoundError(f"Data root not found: {data_root}. Provide data_zip_url or mount data_root.")

    output_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["S305_AI_DATA_ROOT"] = str(data_root)
    env["S305_AI_OUTPUT_ROOT"] = str(output_root)
    env["PYTHONPATH"] = str(repo_root / "ems" / "ai")
    env.setdefault("CUDA_VISIBLE_DEVICES", "0")

    results: list[dict[str, Any]] = []
    for stage, command in _stage_commands(list(stages)):
        if stage == "site_correction":
            train_path = data_root / "processed" / "splits" / "solar_site_correction_train.csv"
            val_path = data_root / "processed" / "splits" / "solar_site_correction_val.csv"
            if not train_path.exists() or not val_path.exists():
                results.append({"stage": stage, "status": "SKIPPED", "reason": "site correction CSV files missing"})
                continue

        result = _run_command(command, env=env, cwd=repo_root)
        result["stage"] = stage
        result["status"] = "COMPLETED" if result["returncode"] == 0 else "FAILED"
        results.append(result)
        if result["returncode"] != 0:
            break

    artifact_zip = WORKSPACE / "output" / "ems_ai_training_artifacts.zip"
    _zip_dir(output_root, artifact_zip)

    artifact: dict[str, Any] = {
        "path": str(artifact_zip),
        "bytes": artifact_zip.stat().st_size,
        "uploaded": False,
    }
    if result_upload_url:
        _upload(result_upload_url, artifact_zip)
        artifact["uploaded"] = True
    elif include_artifact_base64 and artifact_zip.stat().st_size <= 5_000_000:
        artifact["base64"] = base64.b64encode(artifact_zip.read_bytes()).decode("ascii")

    metrics = {
        "lightgbm": _read_json_if_exists(output_root / "artifacts" / "solar_kpx_lightgbm" / "metrics.json"),
        "site_correction": _read_json_if_exists(
            output_root / "artifacts" / "solar_site_correction_lightgbm" / "metrics.json"
        ),
    }

    failed = [result for result in results if result.get("status") == "FAILED"]
    return {
        "ok": not failed,
        "task": "train",
        "stages": results,
        "artifact": artifact,
        "metrics": metrics,
    }


def handler(job: dict[str, Any]) -> dict[str, Any]:
    payload = job.get("input", {})
    task = payload.get("task", "train")
    if task == "predict":
        return _predict(payload)
    if task == "predict_capacity_factor":
        return _predict_capacity_factor(payload)
    if task == "predict_satellite_capacity_factor":
        return _predict_satellite_capacity_factor(payload)
    if task == "predict_live_satellite_capacity_factor":
        return _predict_live_satellite_capacity_factor(payload)
    if task == "runtime_check":
        return _runtime_check()
    if task == "train":
        return _train(payload)
    raise ValueError(f"Unknown task: {task}")


if __name__ == "__main__":
    if runpod is None:
        raise RuntimeError("runpod package is required in the serverless container")
    runpod.serverless.start({"handler": handler})
