from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..config import settings


class SiteLoadProfileRepository:
    def __init__(self) -> None:
        self.enabled = settings.ai_db_enabled

    def latest(self, site_id: str) -> dict[str, Any] | None:
        if not self.enabled:
            return None

        import psycopg

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                self._ensure_table(cur)
                cur.execute(
                    """
                    SELECT
                        site_id,
                        prompt_text,
                        prompt_hash,
                        profile_json,
                        source,
                        model_name,
                        profile_version,
                        status,
                        created_at,
                        updated_at
                    FROM public.ai_site_load_profile
                    WHERE site_id = %s
                      AND status = 'ACTIVE'
                    """,
                    (site_id,),
                )
                row = cur.fetchone()
            conn.commit()
        return self._row(row) if row else None

    def upsert(
        self,
        *,
        site_id: str,
        prompt_text: str,
        prompt_hash: str,
        profile_json: dict[str, Any],
        source: str,
        model_name: str | None = None,
        profile_version: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "site_id": site_id,
                "prompt_text": prompt_text,
                "prompt_hash": prompt_hash,
                "profile_json": profile_json,
                "source": source,
                "model_name": model_name,
                "profile_version": profile_version or profile_json.get("schema_version") or "site_profile.v1",
                "status": "ACTIVE",
            }

        import psycopg

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                self._ensure_table(cur)
                cur.execute(
                    """
                    INSERT INTO public.ai_site_load_profile (
                        site_id,
                        prompt_text,
                        prompt_hash,
                        profile_json,
                        source,
                        model_name,
                        profile_version,
                        status,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE', now(), now())
                    ON CONFLICT (site_id) DO UPDATE SET
                        prompt_text = EXCLUDED.prompt_text,
                        prompt_hash = EXCLUDED.prompt_hash,
                        profile_json = EXCLUDED.profile_json,
                        source = EXCLUDED.source,
                        model_name = EXCLUDED.model_name,
                        profile_version = EXCLUDED.profile_version,
                        status = 'ACTIVE',
                        updated_at = now()
                    RETURNING
                        site_id,
                        prompt_text,
                        prompt_hash,
                        profile_json,
                        source,
                        model_name,
                        profile_version,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        site_id,
                        prompt_text,
                        prompt_hash,
                        self._jsonb(profile_json),
                        source,
                        model_name,
                        profile_version or profile_json.get("schema_version") or "site_profile.v1",
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        return self._row(row)

    def _conninfo(self) -> str:
        if settings.ai_database_url:
            return settings.ai_database_url
        if not settings.ai_db_host:
            raise RuntimeError("S305_AI_DB_HOST or S305_AI_DATABASE_URL is required when S305_AI_DB_ENABLED=true")
        if not settings.ai_db_password:
            raise RuntimeError(
                "S305_AI_DB_PASSWORD, AI_DB_PASSWORD, POSTGRES_ROOT_PASSWORD, or AI_PASSWORD "
                "is required when S305_AI_DB_ENABLED=true"
            )
        return (
            f"host={settings.ai_db_host} "
            f"port={settings.ai_db_port} "
            f"dbname={settings.ai_db_name} "
            f"user={settings.ai_db_user} "
            f"password={settings.ai_db_password}"
        )

    @staticmethod
    def _ensure_table(cur: Any) -> None:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS public.ai_site_load_profile (
                site_id TEXT PRIMARY KEY,
                prompt_text TEXT NOT NULL,
                profile_json JSONB NOT NULL,
                source TEXT NOT NULL DEFAULT 'openai',
                model_name TEXT,
                profile_version TEXT NOT NULL DEFAULT 'site_profile.v1',
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            ALTER TABLE public.ai_site_load_profile
            ADD COLUMN IF NOT EXISTS prompt_hash TEXT
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_site_load_profile_status
            ON public.ai_site_load_profile (status)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_site_load_profile_prompt_hash
            ON public.ai_site_load_profile (site_id, prompt_hash)
            """
        )

    @staticmethod
    def _jsonb(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, default=str)

    @staticmethod
    def _json_value(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        return json.loads(value)

    @classmethod
    def _row(cls, row: tuple[Any, ...]) -> dict[str, Any]:
        (
            site_id,
            prompt_text,
            prompt_hash,
            profile_json,
            source,
            model_name,
            profile_version,
            status,
            created_at,
            updated_at,
        ) = row
        return {
            "site_id": site_id,
            "prompt_text": prompt_text,
            "prompt_hash": prompt_hash,
            "profile_json": cls._json_value(profile_json),
            "source": source,
            "model_name": model_name,
            "profile_version": profile_version,
            "status": status,
            "created_at": cls._iso(created_at),
            "updated_at": cls._iso(updated_at),
        }

    @staticmethod
    def _iso(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value is not None else None
