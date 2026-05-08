from __future__ import annotations

import os
from typing import Any

import requests

from ..config import settings


class RunpodClient:
    def __init__(self, *, session: requests.Session | None = None) -> None:
        self.session = session or requests.Session()

    @property
    def enabled(self) -> bool:
        return settings.runpod_enabled and bool(settings.runpod_endpoint_id)

    def run_sync(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("RunPod is disabled or S305_RUNPOD_ENDPOINT_ID is not configured")

        api_key = os.getenv(settings.runpod_api_key_env)
        if not api_key:
            raise RuntimeError(f"Environment variable {settings.runpod_api_key_env} is not set")

        runpod_input = dict(payload)
        runpod_input["task"] = task

        url = f"{settings.runpod_base_url.rstrip('/')}/{settings.runpod_endpoint_id}/runsync"
        response = self.session.post(
            url,
            json={"input": runpod_input},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=settings.runpod_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()

        if body.get("status") == "COMPLETED":
            output = body.get("output")
            if isinstance(output, dict):
                return output
            raise RuntimeError(f"RunPod completed without object output: {body}")

        if "output" in body and isinstance(body["output"], dict) and body["output"].get("ok") is not None:
            return body["output"]

        error = body.get("error") or body.get("output") or body
        raise RuntimeError(f"RunPod job did not complete successfully: {error}")
