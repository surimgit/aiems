from __future__ import annotations

import hashlib
import re
from typing import Any

from ..config import settings
from ..repositories.site_load_profile_repository import SiteLoadProfileRepository
from .site_profile_service import SiteProfileService


class SiteLoadProfileService:
    def __init__(
        self,
        repository: SiteLoadProfileRepository | None = None,
        site_profile_service: SiteProfileService | None = None,
    ) -> None:
        self.repository = repository or SiteLoadProfileRepository()
        self.site_profile_service = site_profile_service or SiteProfileService()

    def save_prompt(self, payload: dict[str, Any]) -> dict[str, Any]:
        site = payload.get("site") or {}
        site_id = str(payload.get("site_id") or site.get("site_id") or "").strip()
        if not site_id:
            raise ValueError("site_id is required")

        prompt_text = self._prompt_text(payload)
        normalized_prompt = self._normalize_prompt(prompt_text)
        prompt_hash = self._prompt_hash(normalized_prompt)
        current = self.repository.latest(site_id)
        force = bool(payload.get("force", False))

        current_hash = self._current_hash(current)
        if current and current_hash == prompt_hash and not force:
            return {
                "ok": True,
                "task": "save_site_load_profile",
                "changed": False,
                "status": "UNCHANGED",
                "site_id": site_id,
                "prompt_hash": prompt_hash,
                "source": current.get("source"),
                "model_name": current.get("model_name"),
                "profile": current.get("profile_json"),
                "updated_at": current.get("updated_at"),
            }

        structure_result = self.site_profile_service.structure(
            {
                "site_id": site_id,
                "site": {**site, "site_id": site_id},
                "text": normalized_prompt,
                "profile": payload.get("profile"),
                "use_openai": payload.get("use_openai", settings.openai_enabled),
                "auth_env": payload.get("auth_env"),
                "model": payload.get("model"),
                "reasoning_effort": payload.get("reasoning_effort"),
                "max_output_tokens": payload.get("max_output_tokens", 1600),
            }
        )
        profile = structure_result["profile"]
        source = structure_result.get("source") or "unknown"
        model_name = self._model_name(profile, payload)
        saved = self.repository.upsert(
            site_id=site_id,
            prompt_text=normalized_prompt,
            prompt_hash=prompt_hash,
            profile_json=profile,
            source=source,
            model_name=model_name,
            profile_version=profile.get("schema_version"),
        )
        return {
            "ok": True,
            "task": "save_site_load_profile",
            "changed": True,
            "status": "UPDATED",
            "site_id": site_id,
            "prompt_hash": prompt_hash,
            "source": source,
            "model_name": model_name,
            "profile": saved.get("profile_json"),
            "updated_at": saved.get("updated_at"),
        }

    def latest(self, payload: dict[str, Any]) -> dict[str, Any]:
        site_id = str(payload.get("site_id") or "").strip()
        if not site_id:
            raise ValueError("site_id is required")
        current = self.repository.latest(site_id)
        if not current:
            return {
                "ok": True,
                "task": "site_load_profile_latest",
                "enabled": self.repository.enabled,
                "found": False,
                "site_id": site_id,
                "profile": None,
            }
        return {
            "ok": True,
            "task": "site_load_profile_latest",
            "enabled": self.repository.enabled,
            "found": True,
            "site_id": site_id,
            "prompt_text": current.get("prompt_text"),
            "prompt_hash": current.get("prompt_hash"),
            "source": current.get("source"),
            "model_name": current.get("model_name"),
            "profile_version": current.get("profile_version"),
            "status": current.get("status"),
            "profile": current.get("profile_json"),
            "created_at": current.get("created_at"),
            "updated_at": current.get("updated_at"),
        }

    @staticmethod
    def _prompt_text(payload: dict[str, Any]) -> str:
        text = payload.get("prompt_text")
        if text is None:
            text = payload.get("text")
        normalized = SiteLoadProfileService._normalize_prompt(str(text or ""))
        if not normalized:
            raise ValueError("prompt_text is required")
        return normalized

    @staticmethod
    def _normalize_prompt(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _prompt_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def _current_hash(cls, current: dict[str, Any] | None) -> str | None:
        if not current:
            return None
        if current.get("prompt_hash"):
            return str(current["prompt_hash"])
        if current.get("prompt_text"):
            return cls._prompt_hash(cls._normalize_prompt(str(current["prompt_text"])))
        return None

    @staticmethod
    def _model_name(profile: dict[str, Any], payload: dict[str, Any]) -> str | None:
        llm = profile.get("_llm") if isinstance(profile, dict) else None
        if isinstance(llm, dict) and llm.get("model"):
            return str(llm["model"])
        if payload.get("model"):
            return str(payload["model"])
        return settings.openai_model if settings.openai_enabled else None
