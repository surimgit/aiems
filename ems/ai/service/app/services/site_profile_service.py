from __future__ import annotations

import json
from typing import Any

import requests

from ..config import settings
from ..domain.site_profile import normalize_profile, validate_profile
from ..runtime import env_str


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class SiteProfileService:
    def structure(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = payload["text"]
        site = payload.get("site") or {"site_id": payload.get("site_id")}
        if payload.get("profile"):
            profile = normalize_profile(dict(payload["profile"]), site, text)
            source = "provided_profile"
        elif bool(payload.get("use_openai", settings.openai_enabled)):
            profile = normalize_profile(self._call_openai(site, text, payload), site, text)
            source = "openai"
        else:
            profile = normalize_profile(self._fallback_profile(site, text), site, text)
            source = "fallback_rule"

        errors = validate_profile(profile)
        if errors:
            raise ValueError("Invalid site profile: " + "; ".join(errors))
        return {"ok": True, "source": source, "profile": profile}

    def _call_openai(self, site: dict[str, Any], text: str, payload: dict[str, Any]) -> dict[str, Any]:
        key = env_str(payload.get("auth_env") or settings.openai_api_key_env)
        if not key:
            raise RuntimeError(f"Environment variable {payload.get('auth_env') or settings.openai_api_key_env} is not set.")
        model = payload.get("model") or settings.openai_model
        request_payload = {
            "model": model,
            "instructions": (
                "You are a strict JSON transformer for EMS site profiles. "
                "Output only valid JSON matching site_profile.v1."
            ),
            "input": self._prompt(site, text),
            "max_output_tokens": int(payload.get("max_output_tokens", 1600)),
        }
        if payload.get("reasoning_effort"):
            request_payload["reasoning"] = {"effort": payload["reasoning_effort"]}
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=request_payload,
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        profile = json.loads(self._extract_response_text(body))
        profile["_llm"] = {"model": model, "response_id": body.get("id"), "status": body.get("status")}
        return profile

    @staticmethod
    def _fallback_profile(site: dict[str, Any], text: str) -> dict[str, Any]:
        lowered = text.lower()
        site_type = "factory" if any(word in text for word in ("공장", "생산", "라인")) else "unknown"
        critical = "critical" if any(word in text for word in ("병원", "필수", "중요", "정전")) else "medium"
        weekday_bias = 0.15 if any(word in text for word in ("평일", "업무", "근무")) else 0.0
        night_bias = -0.25 if any(word in text for word in ("야간", "밤", "퇴근")) else 0.0
        summer_bias = 0.15 if any(word in lowered for word in ("냉방", "에어컨", "summer")) else 0.0
        return {
            "schema_version": "site_profile.v1",
            "site_id": site.get("site_id"),
            "profile_version": site.get("profile_version", "v1"),
            "site_type": site_type,
            "components": [],
            "seasonal_adjustments": [],
            "operational_constraints": [],
            "forecast_context_features": {
                "weekday_load_bias": weekday_bias,
                "weekend_load_bias": 0.0,
                "night_load_bias": night_bias,
                "summer_load_bias": summer_bias,
                "critical_load_level": critical,
            },
            "assumptions": ["OpenAI 비활성화 상태에서 규칙 기반 fallback으로 생성됨"],
            "warnings": [],
        }

    @staticmethod
    def _extract_response_text(payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"].strip().strip("`")
        chunks: list[str] = []
        for item in payload.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    chunks.append(content["text"])
        text = "\n".join(chunks).strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        return text

    @staticmethod
    def _prompt(site: dict[str, Any], text: str) -> str:
        return (
            "Convert Korean site/operator text into strict JSON for EMS AI forecasting.\n"
            "Required schema_version is site_profile.v1. Return JSON only.\n"
            "Bias fields must be numeric in [-1.0, 1.0].\n"
            f"Site metadata: {json.dumps(site, ensure_ascii=False)}\n"
            f"Operator text: {text}"
        )

