from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import pandas as pd
import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect NASA POWER hourly global site weather/solar data.")
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/nasa_power_global_sites.yaml",
        help="Path to YAML config.",
    )
    parser.add_argument("--start-date", help="Override range.start_date, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="Override range.end_date, YYYY-MM-DD.")
    parser.add_argument(
        "--provider",
        choices=["auto", "api", "s3"],
        help="Override request.provider. auto tries S3 first, then API.",
    )
    parser.add_argument("--refresh", action="store_true", help="Ignore existing processed CSV files.")
    parser.add_argument("--no-db", action="store_true", help="Disable DB upsert for file-only smoke tests.")
    return parser.parse_args()


def resolve_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def load_config(path: str | Path) -> dict[str, Any]:
    with resolve_path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def apply_args(config: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.start_date:
        config["range"]["start_date"] = args.start_date
    if args.end_date:
        config["range"]["end_date"] = args.end_date
    if args.provider:
        config["request"]["provider"] = args.provider
    if args.refresh:
        config["storage"]["skip_existing"] = False
    if args.no_db:
        config.setdefault("database", {})["enabled"] = False
    return config


def resolve_database_config(config: dict[str, Any]) -> dict[str, Any]:
    database = dict(config.get("database") or {})
    if not database.get("use_env_overrides", False):
        return database
    env_map = database.get("env") or {}
    for key, env_name in env_map.items():
        value = os.environ.get(env_name)
        if value:
            database[key] = int(value) if key == "port" else value
    return database


def date_token(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")


def range_token(config: dict[str, Any]) -> str:
    return f"{config['range']['start_date']}_{config['range']['end_date']}"


def site_slug(site: dict[str, Any]) -> str:
    return str(site["site_id"]).lower()


def build_paths(config: dict[str, Any], site: dict[str, Any]) -> dict[str, Path]:
    slug = site_slug(site)
    token = range_token(config)
    raw_root = resolve_path(config["storage"]["raw_root"]) / slug
    processed_root = resolve_path(config["storage"]["processed_root"]) / slug
    return {
        "raw_root": raw_root,
        "processed_root": processed_root,
        "raw_json": raw_root / f"{token}.json",
        "hourly_csv": processed_root / f"{token}.csv",
        "metadata": processed_root / "metadata.json",
    }


def ensure_layout(paths: dict[str, Path]) -> None:
    paths["raw_root"].mkdir(parents=True, exist_ok=True)
    paths["processed_root"].mkdir(parents=True, exist_ok=True)


def request_api_site(config: dict[str, Any], site: dict[str, Any]) -> dict[str, Any]:
    request_config = config["request"]
    params = {
        "start": date_token(config["range"]["start_date"]),
        "end": date_token(config["range"]["end_date"]),
        "latitude": site["latitude"],
        "longitude": site["longitude"],
        "community": request_config.get("community", "re"),
        "parameters": ",".join(request_config["parameters"]),
        "format": request_config.get("format", "JSON"),
        "time-standard": request_config.get("time_standard", "utc"),
    }

    retries = int(request_config.get("retries", 3))
    timeout = int(request_config.get("timeout_seconds", 60))
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(request_config["base_url"], params=params, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt == retries:
                raise
            time.sleep(min(attempt * 2, 10))
    raise RuntimeError("Unreachable retry state.")


def request_s3_site(config: dict[str, Any], site: dict[str, Any]) -> pd.DataFrame:
    try:
        import fsspec
        import xarray as xr
    except ImportError as error:
        raise RuntimeError("S3 provider requires fsspec, xarray, and zarr.") from error

    mapper = fsspec.get_mapper(config["s3"]["zarr_url"])
    dataset = xr.open_zarr(store=mapper, consolidated=True)

    lat_name = "lat" if "lat" in dataset.coords else "latitude"
    lon_name = "lon" if "lon" in dataset.coords else "longitude"
    time_name = "time"

    selected = dataset[config["request"]["parameters"]].sel(
        {
            lat_name: site["latitude"],
            lon_name: site["longitude"],
            time_name: slice(config["range"]["start_date"], config["range"]["end_date"]),
        },
        method="nearest",
    )
    frame = selected.to_dataframe().reset_index()
    frame = frame.rename(columns={time_name: "timestamp_utc", lat_name: "source_latitude", lon_name: "source_longitude"})
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True)
    return frame


def payload_to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    parameters = payload.get("properties", {}).get("parameter", {})
    if not parameters:
        raise ValueError("NASA POWER response does not contain properties.parameter.")

    frame = pd.DataFrame(parameters)
    frame.index.name = "timestamp_token"
    frame = frame.reset_index()
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_token"], format="%Y%m%d%H", utc=True)
    return frame.drop(columns=["timestamp_token"])


def add_site_and_baseline_columns(frame: pd.DataFrame, site: dict[str, Any], config: dict[str, Any], provider: str) -> pd.DataFrame:
    pv_config = config["pv_baseline"]
    output = frame.copy()
    output["site_id"] = site["site_id"]
    output["country"] = site["country"]
    output["timezone"] = site["timezone"]
    output["latitude"] = float(site["latitude"])
    output["longitude"] = float(site["longitude"])
    output["installed_capacity_kw"] = float(site["installed_capacity_kw"])
    output["panel_tilt"] = float(site.get("panel_tilt", 0.0))
    output["panel_azimuth"] = float(site.get("panel_azimuth", 180.0))
    output["source_provider"] = provider

    irradiance = pd.to_numeric(output.get("ALLSKY_SFC_SW_DWN"), errors="coerce").clip(lower=0)
    clear_sky = pd.to_numeric(output.get("CLRSKY_SFC_SW_DWN"), errors="coerce").clip(lower=0)
    temperature = pd.to_numeric(output.get("T2M"), errors="coerce")

    output["clear_sky_ratio"] = (irradiance / clear_sky.replace(0, pd.NA)).clip(lower=0, upper=1.5)
    output["temperature_factor"] = (
        1.0
        + float(pv_config["temperature_coefficient_per_c"])
        * (temperature - float(pv_config["reference_temperature_c"]))
    ).clip(
        lower=float(pv_config["min_temperature_factor"]),
        upper=float(pv_config["max_temperature_factor"]),
    )
    output["predicted_solar_kw_baseline"] = (
        float(site["installed_capacity_kw"])
        * (irradiance / float(pv_config["reference_irradiance_w_m2"]))
        * float(pv_config["system_efficiency"])
        * output["temperature_factor"]
    ).clip(lower=0, upper=float(site["installed_capacity_kw"]))

    ordered = [
        "timestamp_utc",
        "site_id",
        "country",
        "timezone",
        "latitude",
        "longitude",
        "installed_capacity_kw",
        "panel_tilt",
        "panel_azimuth",
        "ALLSKY_SFC_SW_DWN",
        "CLRSKY_SFC_SW_DWN",
        "T2M",
        "RH2M",
        "WS10M",
        "PRECTOTCORR",
        "clear_sky_ratio",
        "temperature_factor",
        "predicted_solar_kw_baseline",
        "source_provider",
    ]
    existing = [column for column in ordered if column in output.columns]
    extras = [column for column in output.columns if column not in existing]
    return output[existing + extras].sort_values("timestamp_utc")


def write_outputs(
    paths: dict[str, Path],
    frame: pd.DataFrame,
    site: dict[str, Any],
    config: dict[str, Any],
    provider: str,
    raw_payload: dict[str, Any] | None = None,
) -> None:
    if raw_payload is not None and config["storage"].get("save_raw_response", True):
        paths["raw_json"].write_text(json.dumps(raw_payload, ensure_ascii=True), encoding="utf-8")

    if config["storage"].get("save_hourly_csv", True):
        frame.to_csv(paths["hourly_csv"], index=False, encoding="utf-8")

    metadata = {
        "site_id": site["site_id"],
        "provider": provider,
        "range": config["range"],
        "rows": int(len(frame)),
        "parameters": config["request"]["parameters"],
        "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    paths["metadata"].write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding="utf-8")


def connect_db(config: dict[str, Any]):
    database = resolve_database_config(config)
    if not database.get("enabled", False):
        return None
    if database.get("load_method", "direct") == "docker_exec":
        return DockerPsqlConnection(database)
    try:
        from pg8000.dbapi import connect
    except ImportError as error:
        raise RuntimeError("DB upsert requires pg8000. Install ems/ai/requirements-train.txt first.") from error
    return connect(
        host=database["host"],
        port=int(database["port"]),
        database=database["database"],
        user=database["user"],
        password=database["password"],
    )


class DockerPsqlConnection:
    def __init__(self, database: dict[str, Any]):
        self.database = database
        self.container = database.get("docker_container", "timescaledb")
        self.db_name = database["database"]
        self.user = database["user"]

    def close(self) -> None:
        return None

    def execute(self, sql: str) -> None:
        subprocess.run(
            ["docker", "exec", self.container, "psql", "-U", self.user, "-d", self.db_name, "-v", "ON_ERROR_STOP=1", "-c", sql],
            check=True,
        )

    def copy_file_to_container(self, local_path: Path, container_path: str) -> None:
        subprocess.run(["docker", "cp", str(local_path), f"{self.container}:{container_path}"], check=True)


def migrate_db(connection) -> None:
    if isinstance(connection, DockerPsqlConnection):
        connection.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_site_mapping (
                site_id VARCHAR(64) PRIMARY KEY,
                country VARCHAR(8) NOT NULL,
                timezone VARCHAR(64) NOT NULL,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                installed_capacity_kw DOUBLE PRECISION NOT NULL,
                panel_tilt DOUBLE PRECISION,
                panel_azimuth DOUBLE PRECISION,
                data_source VARCHAR(64) NOT NULL DEFAULT 'nasa_power',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_site_weather_hourly (
                time TIMESTAMPTZ NOT NULL,
                site_id VARCHAR(64) NOT NULL,
                source_provider VARCHAR(64) NOT NULL,
                allsky_sfc_sw_dwn DOUBLE PRECISION,
                clrsky_sfc_sw_dwn DOUBLE PRECISION,
                t2m DOUBLE PRECISION,
                rh2m DOUBLE PRECISION,
                ws10m DOUBLE PRECISION,
                prectotcorr DOUBLE PRECISION,
                clear_sky_ratio DOUBLE PRECISION,
                temperature_factor DOUBLE PRECISION,
                predicted_solar_kw_baseline DOUBLE PRECISION,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (time, site_id)
            )
            """
        )
        connection.execute("SELECT create_hypertable('ai_site_weather_hourly', 'time', if_not_exists => TRUE)")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_site_weather_hourly_site_time "
            "ON ai_site_weather_hourly (site_id, time DESC)"
        )
        return

    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_site_mapping (
                site_id VARCHAR(64) PRIMARY KEY,
                country VARCHAR(8) NOT NULL,
                timezone VARCHAR(64) NOT NULL,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                installed_capacity_kw DOUBLE PRECISION NOT NULL,
                panel_tilt DOUBLE PRECISION,
                panel_azimuth DOUBLE PRECISION,
                data_source VARCHAR(64) NOT NULL DEFAULT 'nasa_power',
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_site_weather_hourly (
                time TIMESTAMPTZ NOT NULL,
                site_id VARCHAR(64) NOT NULL,
                source_provider VARCHAR(64) NOT NULL,
                allsky_sfc_sw_dwn DOUBLE PRECISION,
                clrsky_sfc_sw_dwn DOUBLE PRECISION,
                t2m DOUBLE PRECISION,
                rh2m DOUBLE PRECISION,
                ws10m DOUBLE PRECISION,
                prectotcorr DOUBLE PRECISION,
                clear_sky_ratio DOUBLE PRECISION,
                temperature_factor DOUBLE PRECISION,
                predicted_solar_kw_baseline DOUBLE PRECISION,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (time, site_id)
            )
            """
        )
        cursor.execute("SELECT create_hypertable('ai_site_weather_hourly', 'time', if_not_exists => TRUE)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_site_weather_hourly_site_time "
            "ON ai_site_weather_hourly (site_id, time DESC)"
        )
    connection.commit()


def upsert_site_mapping(connection, site: dict[str, Any]) -> None:
    if isinstance(connection, DockerPsqlConnection):
        values = {
            "site_id": str(site["site_id"]).replace("'", "''"),
            "country": str(site["country"]).replace("'", "''"),
            "timezone": str(site["timezone"]).replace("'", "''"),
            "latitude": float(site["latitude"]),
            "longitude": float(site["longitude"]),
            "installed_capacity_kw": float(site["installed_capacity_kw"]),
            "panel_tilt": float(site.get("panel_tilt", 0.0)),
            "panel_azimuth": float(site.get("panel_azimuth", 180.0)),
        }
        connection.execute(
            f"""
            INSERT INTO ai_site_mapping
                (site_id, country, timezone, latitude, longitude,
                 installed_capacity_kw, panel_tilt, panel_azimuth, data_source, updated_at)
            VALUES
                ('{values["site_id"]}', '{values["country"]}', '{values["timezone"]}',
                 {values["latitude"]}, {values["longitude"]}, {values["installed_capacity_kw"]},
                 {values["panel_tilt"]}, {values["panel_azimuth"]}, 'nasa_power', NOW())
            ON CONFLICT (site_id) DO UPDATE SET
                country = EXCLUDED.country,
                timezone = EXCLUDED.timezone,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                installed_capacity_kw = EXCLUDED.installed_capacity_kw,
                panel_tilt = EXCLUDED.panel_tilt,
                panel_azimuth = EXCLUDED.panel_azimuth,
                data_source = EXCLUDED.data_source,
                updated_at = NOW()
            """
        )
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO ai_site_mapping
                (site_id, country, timezone, latitude, longitude,
                 installed_capacity_kw, panel_tilt, panel_azimuth, data_source, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'nasa_power', NOW())
            ON CONFLICT (site_id) DO UPDATE SET
                country = EXCLUDED.country,
                timezone = EXCLUDED.timezone,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                installed_capacity_kw = EXCLUDED.installed_capacity_kw,
                panel_tilt = EXCLUDED.panel_tilt,
                panel_azimuth = EXCLUDED.panel_azimuth,
                data_source = EXCLUDED.data_source,
                updated_at = NOW()
            """,
            (
                site["site_id"],
                site["country"],
                site["timezone"],
                float(site["latitude"]),
                float(site["longitude"]),
                float(site["installed_capacity_kw"]),
                float(site.get("panel_tilt", 0.0)),
                float(site.get("panel_azimuth", 180.0)),
            ),
        )
    connection.commit()


def nullable_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def upsert_weather_hourly(connection, frame: pd.DataFrame) -> None:
    if isinstance(connection, DockerPsqlConnection):
        with NamedTemporaryFile("w", newline="", suffix=".csv", delete=False, encoding="utf-8") as temp_file:
            writer = csv.writer(temp_file)
            writer.writerow(
                [
                    "time",
                    "site_id",
                    "source_provider",
                    "allsky_sfc_sw_dwn",
                    "clrsky_sfc_sw_dwn",
                    "t2m",
                    "rh2m",
                    "ws10m",
                    "prectotcorr",
                    "clear_sky_ratio",
                    "temperature_factor",
                    "predicted_solar_kw_baseline",
                ]
            )
            for row in frame.itertuples(index=False):
                writer.writerow(
                    [
                        row.timestamp_utc.isoformat(),
                        row.site_id,
                        row.source_provider,
                        nullable_float(getattr(row, "ALLSKY_SFC_SW_DWN", None)),
                        nullable_float(getattr(row, "CLRSKY_SFC_SW_DWN", None)),
                        nullable_float(getattr(row, "T2M", None)),
                        nullable_float(getattr(row, "RH2M", None)),
                        nullable_float(getattr(row, "WS10M", None)),
                        nullable_float(getattr(row, "PRECTOTCORR", None)),
                        nullable_float(getattr(row, "clear_sky_ratio", None)),
                        nullable_float(getattr(row, "temperature_factor", None)),
                        nullable_float(getattr(row, "predicted_solar_kw_baseline", None)),
                    ]
                )
            temp_path = Path(temp_file.name)

        container_path = f"/tmp/{temp_path.name}"
        try:
            connection.copy_file_to_container(temp_path, container_path)
            connection.execute(
                f"""
                CREATE TEMP TABLE tmp_ai_site_weather_hourly (
                    time TIMESTAMPTZ,
                    site_id VARCHAR(64),
                    source_provider VARCHAR(64),
                    allsky_sfc_sw_dwn DOUBLE PRECISION,
                    clrsky_sfc_sw_dwn DOUBLE PRECISION,
                    t2m DOUBLE PRECISION,
                    rh2m DOUBLE PRECISION,
                    ws10m DOUBLE PRECISION,
                    prectotcorr DOUBLE PRECISION,
                    clear_sky_ratio DOUBLE PRECISION,
                    temperature_factor DOUBLE PRECISION,
                    predicted_solar_kw_baseline DOUBLE PRECISION
                );
                COPY tmp_ai_site_weather_hourly FROM '{container_path}' WITH (FORMAT csv, HEADER true);
                INSERT INTO ai_site_weather_hourly
                    (time, site_id, source_provider,
                     allsky_sfc_sw_dwn, clrsky_sfc_sw_dwn, t2m, rh2m, ws10m, prectotcorr,
                     clear_sky_ratio, temperature_factor, predicted_solar_kw_baseline)
                SELECT
                    time, site_id, source_provider,
                    allsky_sfc_sw_dwn, clrsky_sfc_sw_dwn, t2m, rh2m, ws10m, prectotcorr,
                    clear_sky_ratio, temperature_factor, predicted_solar_kw_baseline
                FROM tmp_ai_site_weather_hourly
                ON CONFLICT (time, site_id) DO UPDATE SET
                    source_provider = EXCLUDED.source_provider,
                    allsky_sfc_sw_dwn = EXCLUDED.allsky_sfc_sw_dwn,
                    clrsky_sfc_sw_dwn = EXCLUDED.clrsky_sfc_sw_dwn,
                    t2m = EXCLUDED.t2m,
                    rh2m = EXCLUDED.rh2m,
                    ws10m = EXCLUDED.ws10m,
                    prectotcorr = EXCLUDED.prectotcorr,
                    clear_sky_ratio = EXCLUDED.clear_sky_ratio,
                    temperature_factor = EXCLUDED.temperature_factor,
                    predicted_solar_kw_baseline = EXCLUDED.predicted_solar_kw_baseline
                """
            )
        finally:
            temp_path.unlink(missing_ok=True)
        return

    rows = [
        (
            row.timestamp_utc.to_pydatetime(),
            row.site_id,
            row.source_provider,
            nullable_float(getattr(row, "ALLSKY_SFC_SW_DWN", None)),
            nullable_float(getattr(row, "CLRSKY_SFC_SW_DWN", None)),
            nullable_float(getattr(row, "T2M", None)),
            nullable_float(getattr(row, "RH2M", None)),
            nullable_float(getattr(row, "WS10M", None)),
            nullable_float(getattr(row, "PRECTOTCORR", None)),
            nullable_float(getattr(row, "clear_sky_ratio", None)),
            nullable_float(getattr(row, "temperature_factor", None)),
            nullable_float(getattr(row, "predicted_solar_kw_baseline", None)),
        )
        for row in frame.itertuples(index=False)
    ]
    if not rows:
        return

    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO ai_site_weather_hourly
                (time, site_id, source_provider,
                 allsky_sfc_sw_dwn, clrsky_sfc_sw_dwn, t2m, rh2m, ws10m, prectotcorr,
                 clear_sky_ratio, temperature_factor, predicted_solar_kw_baseline)
            VALUES %s
            ON CONFLICT (time, site_id) DO UPDATE SET
                source_provider = EXCLUDED.source_provider,
                allsky_sfc_sw_dwn = EXCLUDED.allsky_sfc_sw_dwn,
                clrsky_sfc_sw_dwn = EXCLUDED.clrsky_sfc_sw_dwn,
                t2m = EXCLUDED.t2m,
                rh2m = EXCLUDED.rh2m,
                ws10m = EXCLUDED.ws10m,
                prectotcorr = EXCLUDED.prectotcorr,
                clear_sky_ratio = EXCLUDED.clear_sky_ratio,
                temperature_factor = EXCLUDED.temperature_factor,
                predicted_solar_kw_baseline = EXCLUDED.predicted_solar_kw_baseline
            """,
            rows,
        )
    connection.commit()


def collect_site(config: dict[str, Any], site: dict[str, Any], db_connection=None) -> Path:
    paths = build_paths(config, site)
    ensure_layout(paths)

    if config["storage"].get("skip_existing", True) and paths["hourly_csv"].exists():
        print(f"Skip existing cache: {site['site_id']} -> {paths['hourly_csv']}")
        if db_connection is not None:
            frame = pd.read_csv(paths["hourly_csv"], parse_dates=["timestamp_utc"])
            upsert_site_mapping(db_connection, site)
            upsert_weather_hourly(db_connection, frame)
            print(f"Upserted existing cache to DB: {site['site_id']} rows={len(frame)}")
        return paths["hourly_csv"]

    provider = config["request"].get("provider", "auto")
    raw_payload = None
    if provider in {"auto", "s3"}:
        try:
            frame = request_s3_site(config, site)
            frame = add_site_and_baseline_columns(frame, site, config, "nasa_power_s3")
            write_outputs(paths, frame, site, config, "nasa_power_s3")
            if db_connection is not None:
                upsert_site_mapping(db_connection, site)
                upsert_weather_hourly(db_connection, frame)
            print(f"Collected via S3: {site['site_id']} rows={len(frame)}")
            return paths["hourly_csv"]
        except Exception as error:
            if provider == "s3":
                raise
            print(f"S3 unavailable for {site['site_id']}; fallback to API: {error}")

    raw_payload = request_api_site(config, site)
    frame = payload_to_frame(raw_payload)
    frame = add_site_and_baseline_columns(frame, site, config, "nasa_power_api")
    write_outputs(paths, frame, site, config, "nasa_power_api", raw_payload=raw_payload)
    if db_connection is not None:
        upsert_site_mapping(db_connection, site)
        upsert_weather_hourly(db_connection, frame)
    print(f"Collected via API: {site['site_id']} rows={len(frame)}")
    return paths["hourly_csv"]


def main() -> None:
    args = parse_args()
    config = apply_args(load_config(args.config), args)

    outputs = []
    db_connection = connect_db(config)
    try:
        if db_connection is not None and config.get("database", {}).get("auto_migrate", True):
            migrate_db(db_connection)

        for site in config["sites"]:
            outputs.append(str(collect_site(config, site, db_connection=db_connection)))
            time.sleep(float(config["request"].get("sleep_seconds", 0.0)))
    finally:
        if db_connection is not None:
            db_connection.close()

    manifest_path = resolve_path(config["storage"]["processed_root"]) / "collection_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "source": config["source"],
                "range": config["range"],
                "site_count": len(config["sites"]),
                "outputs": outputs,
                "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            },
            indent=2,
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
