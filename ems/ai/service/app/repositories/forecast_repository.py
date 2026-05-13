from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from ..config import settings


class ForecastRepository:
    def __init__(self) -> None:
        self.enabled = settings.ai_db_enabled

    def save_forecast(self, payload: dict[str, Any], result: dict[str, Any]) -> str | None:
        if not self.enabled:
            return None

        import psycopg

        forecasts = result.get("forecasts") or []
        site_id = self._site_id(payload, forecasts)
        started_at = datetime.now(timezone.utc)

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.ai_forecast_run (
                        site_id,
                        trigger_source,
                        base_time,
                        horizon_hours,
                        model_name,
                        model_version,
                        runpod_endpoint_id,
                        status,
                        input_snapshot_json,
                        request_payload_json,
                        response_payload_json,
                        started_at,
                        completed_at
                    )
                    VALUES (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        now()
                    )
                    RETURNING forecast_run_id
                    """,
                    (
                        site_id,
                        payload.get("trigger_source") or "api",
                        started_at,
                        self._horizon_hours(payload, forecasts),
                        self._model_name(result),
                        self._model_version(result),
                        settings.runpod_endpoint_id,
                        "SUCCESS",
                        self._jsonb(self._input_snapshot(payload)),
                        self._jsonb(payload),
                        self._jsonb(result),
                        started_at,
                    ),
                )
                run_id = cur.fetchone()[0]
                self._insert_points(cur, run_id, site_id, forecasts)
                self._insert_event(
                    cur,
                    run_id,
                    "FORECAST_SAVED",
                    "Forecast result saved",
                    {"site_id": site_id, "rows": len(forecasts)},
                )
            conn.commit()
        return str(run_id)

    def save_event(
        self,
        forecast_run_id: str | UUID | None,
        event_type: str,
        message: str | None = None,
        payload_json: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return

        import psycopg

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                self._insert_event(cur, forecast_run_id, event_type, message, payload_json or {})
            conn.commit()

    def save_actuals(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "matched": 0, "skipped": 0, "errors": []}

        import psycopg

        site_id = payload.get("site_id")
        source = payload.get("actual_source") or payload.get("source") or "manual"
        actuals = payload.get("actuals") or []
        matched = 0
        skipped = 0
        errors: list[dict[str, Any]] = []

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                for row in actuals:
                    row_site_id = row.get("site_id") or site_id
                    target_time = row.get("target_time") or row.get("actual_time")
                    if not row_site_id or not target_time:
                        skipped += 1
                        errors.append({"row": row, "error": "site_id and target_time/actual_time are required"})
                        continue

                    point = self._find_forecast_point(
                        cur,
                        site_id=str(row_site_id),
                        target_time=str(target_time),
                        forecast_run_id=row.get("forecast_run_id") or payload.get("forecast_run_id"),
                    )
                    if not point:
                        skipped += 1
                        errors.append({"site_id": row_site_id, "target_time": target_time, "error": "forecast point not found"})
                        continue

                    forecast_point_id, forecast_run_id = point
                    cur.execute(
                        """
                        INSERT INTO public.ai_forecast_actual (
                            forecast_point_id,
                            actual_time,
                            actual_solar_kw,
                            actual_load_kw,
                            actual_net_load_kw,
                            actual_source,
                            raw_actual_json,
                            matched_at
                        )
                        VALUES (%s, %s::timestamptz, %s, %s, %s, %s, %s, now())
                        ON CONFLICT (forecast_point_id) DO UPDATE SET
                            actual_time = EXCLUDED.actual_time,
                            actual_solar_kw = EXCLUDED.actual_solar_kw,
                            actual_load_kw = EXCLUDED.actual_load_kw,
                            actual_net_load_kw = EXCLUDED.actual_net_load_kw,
                            actual_source = EXCLUDED.actual_source,
                            raw_actual_json = EXCLUDED.raw_actual_json,
                            matched_at = now()
                        """,
                        (
                            forecast_point_id,
                            row.get("actual_time") or target_time,
                            self._optional_float(row.get("actual_solar_kw")),
                            self._optional_float(row.get("actual_load_kw")),
                            self._actual_net_load(row),
                            row.get("actual_source") or source,
                            self._jsonb(row),
                        ),
                    )
                    self._insert_event(
                        cur,
                        forecast_run_id,
                        "ACTUAL_MATCHED",
                        "Actual values matched to forecast point",
                        {"forecast_point_id": forecast_point_id, "site_id": row_site_id, "target_time": target_time},
                    )
                    matched += 1
            conn.commit()

        return {"enabled": True, "matched": matched, "skipped": skipped, "errors": errors}

    def latest_forecast(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {
                "enabled": False,
                "found": False,
                "forecast_run_id": None,
                "forecasts": [],
                "recommendations": [],
            }

        import psycopg

        site_id = payload.get("site_id")
        if not site_id:
            raise ValueError("site_id is required")

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        forecast_run_id,
                        site_id,
                        trigger_source,
                        base_time,
                        horizon_hours,
                        model_name,
                        model_version,
                        status,
                        response_payload_json,
                        created_at,
                        completed_at
                    FROM public.ai_forecast_run
                    WHERE site_id = %s
                      AND status = 'SUCCESS'
                    ORDER BY completed_at DESC NULLS LAST, created_at DESC
                    LIMIT 1
                    """,
                    (site_id,),
                )
                run = cur.fetchone()
                if not run:
                    return {
                        "enabled": True,
                        "found": False,
                        "forecast_run_id": None,
                        "forecasts": [],
                        "recommendations": [],
                    }

                forecast_run_id = run[0]
                cur.execute(
                    """
                    SELECT
                        forecast_point_id,
                        site_id,
                        target_time,
                        horizon_step,
                        predicted_solar_kw,
                        predicted_load_kw,
                        predicted_net_load_kw,
                        confidence,
                        raw_output_json
                    FROM public.ai_forecast_point
                    WHERE forecast_run_id = %s
                    ORDER BY horizon_step ASC, target_time ASC
                    """,
                    (forecast_run_id,),
                )
                points = cur.fetchall()

        response_payload = self._json_value(run[8]) or {}
        forecasts = [self._forecast_point_row(row) for row in points]
        return {
            "enabled": True,
            "found": True,
            "forecast_run_id": str(forecast_run_id),
            "site_id": run[1],
            "trigger_source": run[2],
            "base_time": run[3].isoformat() if run[3] else None,
            "horizon_hours": run[4],
            "model_name": run[5],
            "model_version": run[6],
            "status": run[7],
            "created_at": run[9].isoformat() if run[9] else None,
            "completed_at": run[10].isoformat() if run[10] else None,
            "forecasts": forecasts,
            "recommendations": response_payload.get("recommendations") or [],
        }

    def forecast_accuracy(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "summary": {}, "rows": []}

        import psycopg

        min_denominator_kw = max(0.001, float(payload.get("min_denominator_kw") or 1.0))
        limit = max(1, min(int(payload.get("limit") or 100), 1000))
        conditions = []
        params: list[Any] = []

        if payload.get("site_id"):
            conditions.append("p.site_id = %s")
            params.append(payload["site_id"])
        if payload.get("forecast_run_id"):
            conditions.append("p.forecast_run_id = %s")
            params.append(payload["forecast_run_id"])
        if payload.get("from_time"):
            conditions.append("p.target_time >= %s::timestamptz")
            params.append(payload["from_time"])
        if payload.get("to_time"):
            conditions.append("p.target_time <= %s::timestamptz")
            params.append(payload["to_time"])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        with psycopg.connect(self._conninfo()) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        r.forecast_run_id,
                        p.forecast_point_id,
                        p.site_id,
                        p.target_time,
                        r.model_version,
                        p.predicted_solar_kw,
                        a.actual_solar_kw,
                        p.predicted_load_kw,
                        a.actual_load_kw,
                        p.predicted_net_load_kw,
                        a.actual_net_load_kw,
                        a.actual_source,
                        a.matched_at
                    FROM public.ai_forecast_actual a
                    JOIN public.ai_forecast_point p
                        ON p.forecast_point_id = a.forecast_point_id
                    JOIN public.ai_forecast_run r
                        ON r.forecast_run_id = p.forecast_run_id
                    {where_clause}
                    ORDER BY p.target_time DESC
                    LIMIT %s
                    """,
                    params,
                )
                records = cur.fetchall()

        rows = [self._accuracy_row(record, min_denominator_kw) for record in records]
        return {"enabled": True, "summary": self._accuracy_summary(rows), "rows": rows}

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
    def _insert_points(cur: Any, run_id: UUID, site_id: str, forecasts: list[dict[str, Any]]) -> None:
        for index, row in enumerate(forecasts):
            target_time = row.get("target_time")
            if not target_time:
                continue
            cur.execute(
                """
                INSERT INTO public.ai_forecast_point (
                    forecast_run_id,
                    site_id,
                    target_time,
                    horizon_step,
                    predicted_solar_kw,
                    predicted_load_kw,
                    predicted_net_load_kw,
                    confidence,
                    raw_output_json
                )
                VALUES (%s, %s, %s::timestamptz, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    row.get("site_id") or site_id,
                    target_time,
                    index,
                    ForecastRepository._optional_float(row.get("predicted_solar_kw")),
                    ForecastRepository._optional_float(row.get("predicted_load_kw")),
                    ForecastRepository._optional_float(row.get("predicted_net_load_kw")),
                    ForecastRepository._confidence(row),
                    ForecastRepository._jsonb(row),
                ),
            )

    @staticmethod
    def _insert_event(
        cur: Any,
        forecast_run_id: str | UUID | None,
        event_type: str,
        message: str | None,
        payload_json: dict[str, Any],
    ) -> None:
        cur.execute(
            """
            INSERT INTO public.ai_inference_event (
                forecast_run_id,
                event_type,
                message,
                payload_json
            )
            VALUES (%s, %s, %s, %s)
            """,
            (forecast_run_id, event_type, message, ForecastRepository._jsonb(payload_json)),
        )

    @staticmethod
    def _find_forecast_point(
        cur: Any,
        site_id: str,
        target_time: str,
        forecast_run_id: str | UUID | None = None,
    ) -> tuple[int, UUID] | None:
        params: list[Any] = [site_id, target_time]
        run_filter = ""
        if forecast_run_id:
            run_filter = "AND p.forecast_run_id = %s"
            params.append(forecast_run_id)

        cur.execute(
            f"""
            SELECT p.forecast_point_id, p.forecast_run_id
            FROM public.ai_forecast_point p
            JOIN public.ai_forecast_run r
                ON r.forecast_run_id = p.forecast_run_id
            WHERE p.site_id = %s
              AND p.target_time = %s::timestamptz
              {run_filter}
            ORDER BY r.created_at DESC
            LIMIT 1
            """,
            params,
        )
        return cur.fetchone()

    @staticmethod
    def _accuracy_row(record: tuple[Any, ...], min_denominator_kw: float) -> dict[str, Any]:
        (
            forecast_run_id,
            forecast_point_id,
            site_id,
            target_time,
            model_version,
            predicted_solar_kw,
            actual_solar_kw,
            predicted_load_kw,
            actual_load_kw,
            predicted_net_load_kw,
            actual_net_load_kw,
            actual_source,
            matched_at,
        ) = record
        solar = ForecastRepository._accuracy_metric(predicted_solar_kw, actual_solar_kw, min_denominator_kw)
        load = ForecastRepository._accuracy_metric(predicted_load_kw, actual_load_kw, min_denominator_kw)
        net_load = ForecastRepository._accuracy_metric(predicted_net_load_kw, actual_net_load_kw, min_denominator_kw)
        return {
            "forecast_run_id": str(forecast_run_id),
            "forecast_point_id": int(forecast_point_id),
            "site_id": site_id,
            "target_time": target_time.isoformat() if target_time else None,
            "model_version": model_version,
            "actual_source": actual_source,
            "matched_at": matched_at.isoformat() if matched_at else None,
            "solar": solar,
            "load": load,
            "net_load": net_load,
            "overall_accuracy_percent": ForecastRepository._average(
                [
                    solar.get("accuracy_percent"),
                    load.get("accuracy_percent"),
                    net_load.get("accuracy_percent"),
                ]
            ),
        }

    @staticmethod
    def _accuracy_metric(predicted: Any, actual: Any, min_denominator_kw: float) -> dict[str, float | None]:
        predicted_value = ForecastRepository._optional_float(predicted)
        actual_value = ForecastRepository._optional_float(actual)
        if predicted_value is None or actual_value is None:
            return {
                "predicted_kw": predicted_value,
                "actual_kw": actual_value,
                "error_kw": None,
                "absolute_error_kw": None,
                "absolute_percentage_error_percent": None,
                "accuracy_percent": None,
            }
        error_kw = actual_value - predicted_value
        absolute_error_kw = abs(error_kw)
        denominator = max(abs(actual_value), min_denominator_kw)
        ape = absolute_error_kw / denominator * 100.0
        accuracy = max(0.0, min(100.0, 100.0 - ape))
        return {
            "predicted_kw": predicted_value,
            "actual_kw": actual_value,
            "error_kw": error_kw,
            "absolute_error_kw": absolute_error_kw,
            "absolute_percentage_error_percent": ape,
            "accuracy_percent": accuracy,
        }

    @staticmethod
    def _accuracy_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "matched_points": len(rows),
            "overall_accuracy_percent": ForecastRepository._average(
                [row.get("overall_accuracy_percent") for row in rows]
            ),
            "solar": ForecastRepository._metric_summary(rows, "solar"),
            "load": ForecastRepository._metric_summary(rows, "load"),
            "net_load": ForecastRepository._metric_summary(rows, "net_load"),
        }

    @staticmethod
    def _metric_summary(rows: list[dict[str, Any]], key: str) -> dict[str, float | int | None]:
        metrics = [row[key] for row in rows if row.get(key)]
        return {
            "count": sum(1 for metric in metrics if metric.get("accuracy_percent") is not None),
            "accuracy_percent": ForecastRepository._average([metric.get("accuracy_percent") for metric in metrics]),
            "mae_kw": ForecastRepository._average([metric.get("absolute_error_kw") for metric in metrics]),
            "mape_percent": ForecastRepository._average(
                [metric.get("absolute_percentage_error_percent") for metric in metrics]
            ),
            "bias_kw": ForecastRepository._average([metric.get("error_kw") for metric in metrics]),
        }

    @staticmethod
    def _average(values: list[Any]) -> float | None:
        numeric_values = [float(value) for value in values if value is not None]
        if not numeric_values:
            return None
        return sum(numeric_values) / len(numeric_values)

    @staticmethod
    def _jsonb(value: Any) -> Any:
        from psycopg.types.json import Jsonb

        return Jsonb(value, dumps=lambda data: json.dumps(data, default=str, ensure_ascii=False))

    @staticmethod
    def _site_id(payload: dict[str, Any], forecasts: list[dict[str, Any]]) -> str:
        site = payload.get("site") or {}
        if payload.get("site_id"):
            return str(payload["site_id"])
        if site.get("site_id"):
            return str(site["site_id"])
        for row in forecasts:
            if row.get("site_id"):
                return str(row["site_id"])
        return "UNKNOWN"

    @staticmethod
    def _horizon_hours(payload: dict[str, Any], forecasts: list[dict[str, Any]]) -> int:
        periods = payload.get("periods") or len(payload.get("target_times") or []) or len(forecasts) or 1
        frequency_hours = float(payload.get("frequency_hours") or 1.0)
        return max(1, int(math.ceil(float(periods) * frequency_hours)))

    @staticmethod
    def _model_name(result: dict[str, Any]) -> str:
        if result.get("solar_result") and result["solar_result"].get("task"):
            return str(result["solar_result"]["task"])
        if result.get("load_result") and result["load_result"].get("task"):
            return str(result["load_result"]["task"])
        return "forecast"

    @staticmethod
    def _model_version(result: dict[str, Any]) -> str | None:
        for row in result.get("forecasts") or []:
            if row.get("solar_model_version") and row.get("load_model_version"):
                return f"solar={row['solar_model_version']};load={row['load_model_version']}"
            if row.get("solar_model_version"):
                return str(row["solar_model_version"])
            if row.get("load_model_version"):
                return str(row["load_model_version"])
        return None

    @staticmethod
    def _input_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "site_id": payload.get("site_id") or (payload.get("site") or {}).get("site_id"),
            "site": payload.get("site"),
            "start_time": payload.get("start_time"),
            "target_times": payload.get("target_times"),
            "periods": payload.get("periods"),
            "frequency_hours": payload.get("frequency_hours"),
            "history_defaults": payload.get("history_defaults"),
            "site_profile": payload.get("site_profile"),
        }

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _actual_net_load(row: dict[str, Any]) -> float | None:
        if row.get("actual_net_load_kw") is not None:
            return ForecastRepository._optional_float(row.get("actual_net_load_kw"))
        if row.get("actual_load_kw") is None or row.get("actual_solar_kw") is None:
            return None
        return float(row["actual_load_kw"]) - float(row["actual_solar_kw"])

    @staticmethod
    def _confidence(row: dict[str, Any]) -> float | None:
        confidence = row.get("confidence") or row.get("solar_confidence")
        if confidence is None:
            return None
        return float(confidence)

    @staticmethod
    def _json_value(value: Any) -> dict[str, Any] | list[Any] | None:
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            return json.loads(value)
        return value

    @staticmethod
    def _forecast_point_row(record: tuple[Any, ...]) -> dict[str, Any]:
        (
            forecast_point_id,
            site_id,
            target_time,
            horizon_step,
            predicted_solar_kw,
            predicted_load_kw,
            predicted_net_load_kw,
            confidence,
            raw_output_json,
        ) = record
        raw_output = ForecastRepository._json_value(raw_output_json) or {}
        row = dict(raw_output) if isinstance(raw_output, dict) else {}
        row.update({
            "forecast_point_id": int(forecast_point_id),
            "site_id": site_id,
            "target_time": target_time.isoformat() if target_time else None,
            "horizon_step": int(horizon_step) if horizon_step is not None else None,
            "predicted_solar_kw": ForecastRepository._optional_float(predicted_solar_kw),
            "predicted_load_kw": ForecastRepository._optional_float(predicted_load_kw),
            "predicted_net_load_kw": ForecastRepository._optional_float(predicted_net_load_kw),
            "confidence": ForecastRepository._optional_float(confidence),
        })
        return row
