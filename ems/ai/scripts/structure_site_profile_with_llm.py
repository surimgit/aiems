from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
ALLOWED_USAGE_LEVELS = {"low", "medium", "high", "critical"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert free-text site context into a structured EMS AI profile.")
    parser.add_argument("--config", default="ems/ai/configs/ops/llm_site_profile_example.yaml")
    parser.add_argument("--text", default=None, help="Free-text site/operator context. Overrides config input.text.")
    parser.add_argument("--input-file", default=None, help="UTF-8 text file containing site/operator context.")
    parser.add_argument("--output", default=None, help="Output JSON path. Overrides config output.profile_path.")
    parser.add_argument("--validate-only", action="store_true", help="Validate an existing JSON file from --output.")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def load_env_file(config: dict[str, Any]) -> None:
    env_file = config.get("openai", {}).get("env_file")
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


def input_text(args: argparse.Namespace, config: dict[str, Any]) -> str:
    if args.text:
        return args.text
    if args.input_file:
        return Path(args.input_file).read_text(encoding="utf-8")
    text = config.get("input", {}).get("text")
    if not text:
        raise ValueError("No input text supplied. Use --text, --input-file, or input.text in config.")
    return str(text)


def output_path(args: argparse.Namespace, config: dict[str, Any]) -> Path:
    path = args.output or config.get("output", {}).get("profile_path")
    if not path:
        site_id = config.get("site", {}).get("site_id", "unknown_site")
        path = f"ems/ai/outputs/site_profiles/{site_id}_profile.json"
    return Path(path)


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


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def profile_prompt(site: dict[str, Any], text: str) -> str:
    schema_hint = {
        "schema_version": "site_profile.v1",
        "site_id": site.get("site_id"),
        "profile_version": site.get("profile_version", "v1"),
        "site_type": "office|hospital|factory|campus|residential|commercial|unknown",
        "components": [
            {
                "type": "office|operating_room|hvac|refrigerator|production_line|etc",
                "count": 1,
                "criticality": "low|medium|high|critical",
                "schedule": {
                    "days": "weekday|weekend|daily|custom|unknown",
                    "hours": [9, 10, 11],
                    "season": "spring|summer|fall|winter|all|unknown",
                    "usage_level": "low|medium|high|critical",
                },
            }
        ],
        "seasonal_adjustments": [
            {"season": "summer", "load_bias": "positive|neutral|negative", "reason": "cooling_load"}
        ],
        "operational_constraints": [
            {"type": "must_keep_power|can_shed|priority_load", "description": "short Korean text"}
        ],
        "forecast_context_features": {
            "weekday_load_bias": 0.0,
            "weekend_load_bias": 0.0,
            "night_load_bias": 0.0,
            "summer_load_bias": 0.0,
            "critical_load_level": "low|medium|high|critical",
        },
        "assumptions": ["short Korean text"],
        "warnings": ["short Korean text"],
    }
    return (
        "Convert the Korean site/operator description into strict JSON for EMS AI forecasting.\n"
        "Return JSON only. Do not wrap in markdown. Do not invent exact sensor values.\n"
        "Use numeric bias fields in the range -1.0 to 1.0. Use 0.0 when unknown.\n"
        "Keep all descriptions concise Korean.\n"
        f"Required shape example:\n{json.dumps(schema_hint, ensure_ascii=False, indent=2)}\n\n"
        f"Site metadata:\n{json.dumps(site, ensure_ascii=False)}\n\n"
        f"Operator text:\n{text}"
    )


def call_openai(config: dict[str, Any], text: str) -> dict[str, Any]:
    openai = config.get("openai", {})
    key = env_value(openai.get("auth_env", "OPENAI_API_KEY"))
    model = os.getenv(openai.get("model_env", "OPENAI_MODEL")) or openai.get("default_model", "gpt-5-nano")
    request_payload: dict[str, Any] = {
        "model": model,
        "instructions": (
            "You are a strict JSON transformer for EMS site profiles. "
            "Output only valid JSON matching the requested shape."
        ),
        "input": profile_prompt(config.get("site", {}), text),
        "max_output_tokens": int(openai.get("max_output_tokens", 1600)),
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
    content = strip_json_fence(extract_response_text(body))
    profile = json.loads(content)
    profile["_llm"] = {"model": model, "response_id": body.get("id"), "status": body.get("status")}
    return profile


def normalize_profile(profile: dict[str, Any], config: dict[str, Any], text: str) -> dict[str, Any]:
    site = config.get("site", {})
    profile.setdefault("schema_version", "site_profile.v1")
    profile.setdefault("site_id", site.get("site_id"))
    profile.setdefault("profile_version", site.get("profile_version", "v1"))
    profile.setdefault("site_type", "unknown")
    profile.setdefault("components", [])
    profile.setdefault("seasonal_adjustments", [])
    profile.setdefault("operational_constraints", [])
    profile.setdefault("forecast_context_features", {})
    profile.setdefault("assumptions", [])
    profile.setdefault("warnings", [])
    features = profile["forecast_context_features"]
    for name in ("weekday_load_bias", "weekend_load_bias", "night_load_bias", "summer_load_bias"):
        features[name] = float(features.get(name, 0.0))
    features.setdefault("critical_load_level", "medium")
    profile["_source"] = {
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    return profile


def validate_profile(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if profile.get("schema_version") != "site_profile.v1":
        errors.append("schema_version must be site_profile.v1")
    for key in ("site_id", "profile_version", "site_type"):
        if not isinstance(profile.get(key), str) or not profile[key].strip():
            errors.append(f"{key} must be a non-empty string")
    if not isinstance(profile.get("components"), list):
        errors.append("components must be a list")
    else:
        for index, component in enumerate(profile["components"]):
            if not isinstance(component, dict):
                errors.append(f"components[{index}] must be an object")
                continue
            if not isinstance(component.get("type"), str) or not component["type"].strip():
                errors.append(f"components[{index}].type must be a non-empty string")
            if "count" in component and (not isinstance(component["count"], int) or component["count"] < 0):
                errors.append(f"components[{index}].count must be a non-negative integer")
            schedule = component.get("schedule", {})
            if schedule and not isinstance(schedule, dict):
                errors.append(f"components[{index}].schedule must be an object")
            usage_level = schedule.get("usage_level") if isinstance(schedule, dict) else None
            if usage_level and usage_level not in ALLOWED_USAGE_LEVELS:
                errors.append(f"components[{index}].schedule.usage_level is invalid: {usage_level}")
    features = profile.get("forecast_context_features")
    if not isinstance(features, dict):
        errors.append("forecast_context_features must be an object")
    else:
        for name in ("weekday_load_bias", "weekend_load_bias", "night_load_bias", "summer_load_bias"):
            value = features.get(name)
            if not isinstance(value, (int, float)) or not -1.0 <= float(value) <= 1.0:
                errors.append(f"forecast_context_features.{name} must be numeric in [-1.0, 1.0]")
        level = features.get("critical_load_level")
        if level not in ALLOWED_USAGE_LEVELS:
            errors.append("forecast_context_features.critical_load_level must be low|medium|high|critical")
    for key in ("seasonal_adjustments", "operational_constraints", "assumptions", "warnings"):
        if not isinstance(profile.get(key), list):
            errors.append(f"{key} must be a list")
    return errors


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    path = output_path(args, config)
    if args.validate_only:
        profile = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_profile(profile)
        if errors:
            raise ValueError("Invalid profile:\n" + "\n".join(f"- {error}" for error in errors))
        print(json.dumps({"ok": True, "profile_path": str(path)}, indent=2, ensure_ascii=False))
        return

    text = input_text(args, config)
    load_env_file(config)
    profile = normalize_profile(call_openai(config, text), config, text)
    errors = validate_profile(profile)
    if errors:
        raise ValueError("Invalid LLM profile:\n" + "\n".join(f"- {error}" for error in errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "profile_path": str(path), "profile": profile}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
