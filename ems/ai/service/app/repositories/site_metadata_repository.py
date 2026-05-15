from __future__ import annotations

from datetime import datetime
from typing import Any

from ..config import settings


class SiteMetadataRepository:
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
                        region,
                        model_region,
                        dong_code,
                        latitude,
                        longitude,
                        installed_capacity_kw,
                        timezone,
                        model_capacity_kw,
                        status,
                        created_at,
                        updated_at
                    FROM public.ai_site_metadata
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
        region: str,
        latitude: float,
        longitude: float,
        installed_capacity_kw: float,
        model_region: str | None = None,
        dong_code: str | None = None,
        timezone: str = "Asia/Seoul",
        model_capacity_kw: float | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "site_id": site_id,
                "region": region,
                "model_region": model_region,
                "dong_code": dong_code,
                "latitude": latitude,
                "longitude": longitude,
                "installed_capacity_kw": installed_capacity_kw,
                "timezone": timezone,
                "model_capacity_kw": model_capacity_kw,
                "status": "ACTIVE",
            }

        import psycopg

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                self._ensure_table(cur)
                cur.execute(
                    """
                    INSERT INTO public.ai_site_metadata (
                        site_id,
                        region,
                        model_region,
                        dong_code,
                        latitude,
                        longitude,
                        installed_capacity_kw,
                        timezone,
                        model_capacity_kw,
                        status,
                        created_at,
                        updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE', now(), now())
                    ON CONFLICT (site_id) DO UPDATE SET
                        region = EXCLUDED.region,
                        model_region = EXCLUDED.model_region,
                        dong_code = EXCLUDED.dong_code,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        installed_capacity_kw = EXCLUDED.installed_capacity_kw,
                        timezone = EXCLUDED.timezone,
                        model_capacity_kw = EXCLUDED.model_capacity_kw,
                        status = 'ACTIVE',
                        updated_at = now()
                    RETURNING
                        site_id,
                        region,
                        model_region,
                        dong_code,
                        latitude,
                        longitude,
                        installed_capacity_kw,
                        timezone,
                        model_capacity_kw,
                        status,
                        created_at,
                        updated_at
                    """,
                    (
                        site_id,
                        region,
                        model_region,
                        dong_code,
                        latitude,
                        longitude,
                        installed_capacity_kw,
                        timezone,
                        model_capacity_kw,
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
            CREATE TABLE IF NOT EXISTS public.ai_site_metadata (
                site_id TEXT PRIMARY KEY,
                region TEXT NOT NULL,
                model_region TEXT,
                dong_code TEXT,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                installed_capacity_kw DOUBLE PRECISION NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'Asia/Seoul',
                model_capacity_kw DOUBLE PRECISION,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        cur.execute(
            """
            ALTER TABLE public.ai_site_metadata
            ADD COLUMN IF NOT EXISTS model_region TEXT
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_site_metadata_status
            ON public.ai_site_metadata (status)
            """
        )

    @classmethod
    def _row(cls, row: tuple[Any, ...]) -> dict[str, Any]:
        (
            site_id,
            region,
            model_region,
            dong_code,
            latitude,
            longitude,
            installed_capacity_kw,
            timezone_name,
            model_capacity_kw,
            status,
            created_at,
            updated_at,
        ) = row
        return {
            "site_id": site_id,
            "region": region,
            "model_region": model_region,
            "dong_code": dong_code,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "installed_capacity_kw": float(installed_capacity_kw),
            "timezone": timezone_name,
            "model_capacity_kw": float(model_capacity_kw) if model_capacity_kw is not None else None,
            "status": status,
            "created_at": cls._iso(created_at),
            "updated_at": cls._iso(updated_at),
        }

    @staticmethod
    def _iso(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value is not None else None
