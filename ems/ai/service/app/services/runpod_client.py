from __future__ import annotations

import os
import time
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

        api_key = self._env_secret(settings.runpod_api_key_env)
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
        if body.get("status") in {"IN_QUEUE", "IN_PROGRESS"} and body.get("id"):
            body = self._wait_for_job(str(body["id"]), api_key)

        if body.get("status") == "COMPLETED":
            output = body.get("output")
            if isinstance(output, dict):
                return output
            raise RuntimeError(f"RunPod completed without object output: {body}")

        if "output" in body and isinstance(body["output"], dict) and body["output"].get("ok") is not None:
            return body["output"]

        error = body.get("error") or body.get("output") or body
        raise RuntimeError(f"RunPod job did not complete successfully: {error}")

    def _wait_for_job(self, job_id: str, api_key: str) -> dict[str, Any]:
        deadline = time.time() + settings.runpod_timeout_seconds
        url = f"{settings.runpod_base_url.rstrip('/')}/{settings.runpod_endpoint_id}/status/{job_id}"

        while time.time() < deadline:
            time.sleep(2.0)
            response = self.session.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=min(30.0, settings.runpod_timeout_seconds),
            )
            response.raise_for_status()
            body = response.json()
            if body.get("status") not in {"IN_QUEUE", "IN_PROGRESS"}:
                return body

        raise TimeoutError(f"RunPod job timed out: {job_id}")

    @staticmethod
    def _env_secret(name: str) -> str | None:
        value = os.getenv(name)
        if value is None:
            return None
        return value.strip().strip('"').strip("'")
