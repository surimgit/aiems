from __future__ import annotations

from typing import Any

from ..repositories.site_metadata_repository import SiteMetadataRepository
from .state_site_metadata_client import StateSiteMetadataClient


class SiteMetadataService:
    def __init__(
        self,
        repository: SiteMetadataRepository | None = None,
        state_client: StateSiteMetadataClient | None = None,
    ) -> None:
        self.repository = repository or SiteMetadataRepository()
        self.state_client = state_client or StateSiteMetadataClient()

    def latest(self, payload: dict[str, Any]) -> dict[str, Any]:
        site_id = str(payload.get("site_id") or "").strip()
        if not site_id:
            raise ValueError("site_id is required")
        current = self.repository.latest(site_id)
        if not current:
            return {
                "ok": True,
                "task": "site_metadata_latest",
                "enabled": self.repository.enabled,
                "found": False,
                "site_id": site_id,
                "site": None,
            }
        return {
            "ok": True,
            "task": "site_metadata_latest",
            "enabled": self.repository.enabled,
            "found": True,
            "site_id": site_id,
            "site": current,
            "status": current.get("status"),
            "created_at": current.get("created_at"),
            "updated_at": current.get("updated_at"),
        }

    def save(self, payload: dict[str, Any]) -> dict[str, Any]:
        site_id = str(payload.get("site_id") or "").strip()
        region = str(payload.get("region") or "").strip()
        if not site_id:
            raise ValueError("site_id is required")
        if not region:
            raise ValueError("region is required")
        site = self.repository.upsert(
            site_id=site_id,
            region=region,
            model_region=self._optional_str(payload.get("model_region")),
            dong_code=self._optional_str(payload.get("dong_code")),
            latitude=float(payload["latitude"]),
            longitude=float(payload["longitude"]),
            installed_capacity_kw=float(payload["installed_capacity_kw"]),
            timezone=str(payload.get("timezone") or "Asia/Seoul"),
            model_capacity_kw=self._optional_float(payload.get("model_capacity_kw")),
        )
        return {
            "ok": True,
            "task": "save_site_metadata",
            "enabled": self.repository.enabled,
            "found": True,
            "site_id": site_id,
            "site": site,
            "status": site.get("status"),
            "created_at": site.get("created_at"),
            "updated_at": site.get("updated_at"),
        }

    def sync_from_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        site_id = str(payload.get("site_id") or "").strip()
        if not site_id:
            raise ValueError("site_id is required")
        current = self.repository.latest(site_id)
        live = self.state_client.fetch(site_id, current)
        if not live:
            return {
                "ok": True,
                "task": "sync_site_metadata",
                "enabled": self.repository.enabled,
                "found": bool(current),
                "source": "ai_site_metadata" if current else "state_api",
                "site_id": site_id,
                "site": current,
                "status": current.get("status") if current else "NOT_FOUND",
                "updated_at": current.get("updated_at") if current else None,
            }
        saved = self._save_site_dict(live)
        return {
            "ok": True,
            "task": "sync_site_metadata",
            "enabled": self.repository.enabled,
            "found": True,
            "source": "state_api",
            "site_id": site_id,
            "site": saved,
            "status": saved.get("status"),
            "updated_at": saved.get("updated_at"),
        }

    def resolve(self, site_id: str) -> dict[str, Any] | None:
        current = self.repository.latest(site_id)
        try:
            live = self.state_client.fetch(site_id, current)
        except Exception as exc:
            if current:
                return {**current, "_source": "ai_site_metadata", "_warning": f"state_metadata_lookup_failed: {exc}"}
            raise
        if live:
            saved = self._save_site_dict(live)
            return {**saved, "_source": "state_api"}
        if current:
            return {**current, "_source": "ai_site_metadata"}
        return None

    def _save_site_dict(self, site: dict[str, Any]) -> dict[str, Any]:
        return self.repository.upsert(
            site_id=str(site["site_id"]),
            region=str(site["region"]),
            model_region=self._optional_str(site.get("model_region")),
            dong_code=self._optional_str(site.get("dong_code")),
            latitude=float(site["latitude"]),
            longitude=float(site["longitude"]),
            installed_capacity_kw=float(site["installed_capacity_kw"]),
            timezone=str(site.get("timezone") or "Asia/Seoul"),
            model_capacity_kw=self._optional_float(site.get("model_capacity_kw")),
        )

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)
