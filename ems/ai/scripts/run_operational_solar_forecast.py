from __future__ import annotations

import argparse
import json
import math
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yaml
from astral import Observer
from astral.sun import elevation

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


RUNPOD_BASE_URL = "https://api.runpod.ai/v2"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build payload, call RunPod, and optionally ask an LLM for ops notes.")
    parser.add_argument("--config", default="ems/ai/configs/ops/operational_solar_forecast_example.yaml")
    parser.add_argument("--output", default="ems/ai/outputs/operational_solar_forecast_result.json")
    parser.add_argument("--skip-runpod", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_env_files(config: dict[str, Any]) -> None:
    for section in ("runpod", "openai"):
        env_file = config.get(section, {}).get("env_file")
        if env_file and load_dotenv is not None:
            load_dotenv(env_file)
        elif env_file:
            with Path(env_file).open("r", encoding="utf-8") as file:
                for line in file:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        continue
                    name, value = stripped.split("=", 1)
                    os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def env_value(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is not set.")
    return value


def parse_time(value: str, timezone_name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed


def target_times(config: dict[str, Any]) -> list[datetime]:
    site = config["site"]
    targets = config["targets"]
    start = parse_time(targets["start_time"], site.get("timezone", "Asia/Seoul"))
    periods = int(targets.get("periods", 1))
    step = timedelta(hours=float(targets.get("frequency_hours", 1)))
    return [start + step * index for index in range(periods)]


def cyclical_features(timestamp: datetime) -> dict[str, float]:
    hour = timestamp.hour
    day_of_year = int(timestamp.strftime("%j"))
    return {
        "hour_of_day_sin": math.sin(2 * math.pi * hour / 24.0),
        "hour_of_day_cos": math.cos(2 * math.pi * hour / 24.0),
        "day_of_year_sin": math.sin(2 * math.pi * day_of_year / 365.25),
        "day_of_year_cos": math.cos(2 * math.pi * day_of_year / 365.25),
    }


def solar_elevation_mid(site: dict[str, Any], timestamp: datetime) -> float:
    observer = Observer(latitude=float(site["latitude"]), longitude=float(site["longitude"]))
    return float(elevation(observer, timestamp))


def load_history_defaults(config: dict[str, Any]) -> dict[str, float]:
    defaults = config.get("history_defaults", {})
    required = [
        "past_capacity_factor",
        "past_capacity_factor_lag_1",
        "past_capacity_factor_lag_24",
        "rolling_mean_cf_3h",
        "rolling_mean_cf_24h",
    ]
    missing = [name for name in required if name not in defaults]
    if missing:
        raise ValueError(f"Missing history defaults: {missing}")
    return {name: float(defaults[name]) for name in required}


def build_runpod_payload(config: dict[str, Any]) -> dict[str, Any]:
    site = config["site"]
    history = load_history_defaults(config)
    features = []
    for timestamp in target_times(config):
        solar_elevation = solar_elevation_mid(site, timestamp)
        features.append(
            {
                "target_time": timestamp.isoformat(),
                "site_id": site.get("site_id"),
                "region": site.get("region"),
                "latitude": float(site["latitude"]),
                "longitude": float(site["longitude"]),
                "timezone": site.get("timezone", "Asia/Seoul"),
                "installed_capacity_kw": float(site["installed_capacity_kw"]),
                "solar_elevation_mid": solar_elevation,
                "is_daylight": 1 if solar_elevation > 0 else 0,
                **history,
                **cyclical_features(timestamp),
            }
        )

    runpod = config["runpod"]
    return {
        "task": "predict_capacity_factor",
        "region": site.get("region"),
        "site_id": site.get("site_id"),
        "installed_capacity_kw": float(site["installed_capacity_kw"]),
        "model_path": runpod.get("model_path"),
        "model_version": runpod.get("model_version"),
        "features": features,
    }


def call_runpod(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    runpod = config["runpod"]
    endpoint_id = runpod.get("endpoint_id") or os.getenv("RUNPOD_ENDPOINT_ID")
    if not endpoint_id:
        raise RuntimeError("RunPod endpoint_id is missing.")
    key = env_value(runpod.get("auth_env", "RUNPOD_KEY"))
    wait_ms = int(runpod.get("wait_ms", 300000))
    url = f"{RUNPOD_BASE_URL}/{endpoint_id}/runsync?wait={wait_ms}"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"input": payload},
        timeout=max(60, wait_ms // 1000 + 30),
    )
    response.raise_for_status()
    return response.json()


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def safe_print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("utf-8", errors="replace").decode("utf-8"))


def call_openai(config: dict[str, Any], runpod_result: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    openai = config.get("openai", {})
    key = env_value(openai.get("auth_env", "OPENAI_API_KEY"))
    model = os.getenv(openai.get("model_env", "OPENAI_MODEL")) or openai.get("default_model", "gpt-5-nano")
    context = {
        "site": config["site"],
        "weather_context": config.get("weather_context", {}),
        "runpod_output": runpod_result.get("output", runpod_result),
        "payload_features": payload.get("features", []),
    }
    instructions = (
        "You are an EMS solar operations assistant. "
        "Write concise Korean operational notes from the provided forecast. "
        "Do not invent measurements. Flag night-zero clamps, low confidence, and weather risks. "
        "If weather_context.source is smoke_test, treat it as a test-run label, not haze or smoke weather."
    )
    request_payload = {
        "model": model,
        "instructions": instructions,
        "input": json.dumps(context, ensure_ascii=False),
        "max_output_tokens": int(openai.get("max_output_tokens", 700)),
    }
    if openai.get("reasoning_effort"):
        request_payload["reasoning"] = {"effort": openai["reasoning_effort"]}

    response = requests.post(
        OPENAI_RESPONSES_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=request_payload,
        timeout=60,
    )
    response.raise_for_status()
    body = response.json()
    return {
        "model": model,
        "text": extract_response_text(body),
        "raw_response_id": body.get("id"),
        "status": body.get("status"),
    }


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    load_env_files(config)
    payload = build_runpod_payload(config)

    runpod_result: dict[str, Any] | None = None
    if not args.skip_runpod:
        runpod_result = call_runpod(config, payload)

    llm_result: dict[str, Any] | None = None
    if not args.skip_llm and config.get("openai", {}).get("enabled", True):
        if runpod_result is None:
            raise RuntimeError("LLM step requires RunPod result unless --skip-llm is used.")
        llm_result = call_openai(config, runpod_result, payload)

    output = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "payload": payload,
        "runpod_result": runpod_result,
        "llm_result": llm_result,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    safe_print_json(output)


if __name__ == "__main__":
    main()
