"""Collect 2025 KMA APIHub ASOS hourly weather for solar regions.

This collector uses the KMA APIHub `kma_sfctm3.php` endpoint and avoids the
`requests` dependency so it can run inside the existing preprocessing venv.
It stores raw monthly responses, parsed monthly CSV/parquet files, and a merged
feature parquet with safe leading numeric weather columns.
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd


DEFAULT_ENV_FILE = Path(r"C:\Users\SSAFY\PycharmProjects\S14P31S305\ems\ai\.env")
DEFAULT_OUTPUT_ROOT = Path(r"C:\Users\SSAFY\Project_Minsu\S305\s305-ai-data")
DEFAULT_ENDPOINT = "https://apihub.kma.go.kr/api/typ01/url/kma_sfctm3.php"

KMA_ASOS_COLUMNS = [
    "TM",
    "STN",
    "WD",
    "WS",
    "GST_WD",
    "GST_WS",
    "GST_TM",
    "PA",
    "PS",
    "PT",
    "PR",
    "TA",
    "TD",
    "HM",
    "PV",
    "RN",
    "RN_DAY",
    "RN_JUN",
    "RN_INT",
    "SD_HR3",
    "SD_DAY",
    "SD_TOT",
    "WC",
    "WP",
    "WW",
    "CA_TOT",
    "CA_MID",
    "CH_MIN",
    "CT",
    "CT_TOP",
    "CT_MID",
    "CT_LOW",
    "VS",
    "SS",
    "SI",
    "ST_GD",
    "TS",
    "TE_005",
    "TE_01",
    "TE_02",
    "TE_03",
    "ST_SEA",
    "WH",
    "BF",
    "IR",
    "IX",
]

REGION_STATIONS = [
    {"region": "서울시", "region_slug": "seoul", "station_id": 108, "station_name": "서울"},
    {"region": "부산시", "region_slug": "busan", "station_id": 159, "station_name": "부산"},
    {"region": "대전시", "region_slug": "daejeon", "station_id": 133, "station_name": "대전"},
    {"region": "울산시", "region_slug": "ulsan", "station_id": 152, "station_name": "울산"},
    {"region": "제주도", "region_slug": "jeju", "station_id": 184, "station_name": "제주"},
]


@dataclass(frozen=True)
class MonthWindow:
    year: int
    month: int

    @property
    def token(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def start_tm(self) -> str:
        return f"{self.year:04d}{self.month:02d}010000"

    @property
    def end_tm(self) -> str:
        last_day = calendar.monthrange(self.year, self.month)[1]
        return f"{self.year:04d}{self.month:02d}{last_day:02d}2359"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def load_env_key(env_file: Path, name: str = "KMA_AUTH_KEY") -> str:
    if name in os.environ and os.environ[name].strip():
        return os.environ[name].strip()

    if not env_file.exists():
        raise FileNotFoundError(env_file)

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == name:
            token = value.strip().strip('"').strip("'")
            if token:
                return token
    raise RuntimeError(f"{name} is not set in {env_file}")


def month_windows(year: int) -> list[MonthWindow]:
    return [MonthWindow(year, month) for month in range(1, 13)]


def request_month(
    *,
    auth_key: str,
    station_id: int,
    window: MonthWindow,
    timeout_seconds: int,
    retries: int,
) -> str:
    params = {
        "tm1": window.start_tm,
        "tm2": window.end_tm,
        "stn": str(station_id),
        "help": "0",
        "authKey": auth_key,
    }
    url = DEFAULT_ENDPOINT + "?" + urlencode(params)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = Request(url, headers={"User-Agent": "s305-ai-kma-asos-collector/1.0"})
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
            text = raw.decode("utf-8", errors="replace")
            if not text.strip():
                raise RuntimeError("empty response")
            return text
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(min(2 * attempt, 6))
    raise RuntimeError(f"failed station={station_id} month={window.token}: {last_error}") from last_error


def parse_asos_text(raw_text: str) -> pd.DataFrame:
    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)

    if not lines:
        raise ValueError("no data lines found")

    frame = pd.read_csv(
        StringIO("\n".join(lines)),
        sep=r"\s+",
        engine="python",
        header=None,
        names=KMA_ASOS_COLUMNS,
    )
    return frame


def clean_numeric(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.columns:
        if column == "TM":
            continue
        out[column] = pd.to_numeric(out[column], errors="coerce")
        out.loc[out[column] <= -900, column] = np.nan
    return out


def add_features(frame: pd.DataFrame, station: dict) -> pd.DataFrame:
    out = clean_numeric(frame)
    out["timestamp_kst"] = pd.to_datetime(out["TM"].astype(str), format="%Y%m%d%H%M", errors="coerce")
    out["region"] = station["region"]
    out["region_slug"] = station["region_slug"]
    out["station_id"] = int(station["station_id"])
    out["station_name"] = station["station_name"]

    # KMA ASOS WD is encoded as a 16-direction code in 10-degree units
    # (e.g. 09 = east, 18 = south, 27 = west, 36 = north).
    wd_code = out["WD"].astype(float)
    ws = out["WS"].astype(float)
    wd_code = wd_code.where(wd_code >= 0)
    ws = ws.where(ws >= 0)
    valid_wind = wd_code.notna() & ws.notna() & (wd_code > 0) & (ws > 0)
    wd_deg = np.mod(wd_code * 10.0, 360.0)
    radians = np.deg2rad(wd_deg)
    out["wind_u"] = (ws * np.sin(radians)).where(valid_wind, 0.0)
    out["wind_v"] = (ws * np.cos(radians)).where(valid_wind, 0.0)
    out["wind_speed_ms"] = ws
    out["wind_dir_deg"] = wd_deg.where(valid_wind, 0.0)
    out["wind_dir_sin"] = np.sin(radians).where(valid_wind, 0.0)
    out["wind_dir_cos"] = np.cos(radians).where(valid_wind, 0.0)

    return out


def station_paths(output_root: Path, station: dict) -> dict[str, Path]:
    root = (
        output_root
        / "raw"
        / "weather"
        / "kma_asos_apihub"
        / station["region_slug"]
        / f"station_{station['station_id']}"
    )
    return {
        "root": root,
        "raw": root / "hourly_raw",
        "csv": root / "hourly_csv",
        "parquet": root / "hourly_parquet",
        "metadata": root / "metadata",
    }


def ensure_paths(paths: dict[str, Path]) -> None:
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)


def collect_station(
    *,
    auth_key: str,
    output_root: Path,
    station: dict,
    windows: list[MonthWindow],
    timeout_seconds: int,
    retries: int,
    sleep_seconds: float,
    overwrite: bool,
) -> tuple[list[pd.DataFrame], list[dict]]:
    paths = station_paths(output_root, station)
    ensure_paths(paths)

    frames = []
    manifest_rows = []
    for window in windows:
        raw_path = paths["raw"] / f"{window.token}.txt"
        csv_path = paths["csv"] / f"{window.token}.csv"
        parquet_path = paths["parquet"] / f"{window.token}.parquet"

        if parquet_path.exists() and not overwrite:
            frame = pd.read_parquet(parquet_path)
            status = "cached"
        else:
            raw_text = request_month(
                auth_key=auth_key,
                station_id=int(station["station_id"]),
                window=window,
                timeout_seconds=timeout_seconds,
                retries=retries,
            )
            raw_path.write_text(raw_text, encoding="utf-8")
            parsed = parse_asos_text(raw_text)
            frame = add_features(parsed, station)
            frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
            frame.to_parquet(parquet_path, index=False)
            status = "downloaded"
            time.sleep(sleep_seconds)

        frames.append(frame)
        manifest_rows.append(
            {
                "region": station["region"],
                "region_slug": station["region_slug"],
                "station_id": int(station["station_id"]),
                "station_name": station["station_name"],
                "month": window.token,
                "rows": int(len(frame)),
                "wd_non_null": int(frame["WD"].notna().sum()),
                "ws_non_null": int(frame["WS"].notna().sum()),
                "status": status,
                "raw_path": str(raw_path),
                "csv_path": str(csv_path),
                "parquet_path": str(parquet_path),
            }
        )
        print(
            f"{station['region']} {station['station_id']} {window.token}: "
            f"{status}, rows={len(frame)}, WD={manifest_rows[-1]['wd_non_null']}, WS={manifest_rows[-1]['ws_non_null']}",
            flush=True,
        )

    station_frame = pd.concat(frames, ignore_index=True)
    station_frame = station_frame.sort_values("timestamp_kst").reset_index(drop=True)
    station_frame.to_parquet(paths["root"] / f"asos_hourly_{station['region_slug']}_{windows[0].year}.parquet", index=False)
    pd.DataFrame(manifest_rows).to_csv(paths["metadata"] / "monthly_manifest.csv", index=False, encoding="utf-8-sig")
    return frames, manifest_rows


def write_outputs(output_root: Path, year: int, frames: list[pd.DataFrame], manifest_rows: list[dict]) -> None:
    processed_dir = output_root / "processed" / "weather" / "kma_asos_apihub"
    processed_dir.mkdir(parents=True, exist_ok=True)

    all_frame = pd.concat(frames, ignore_index=True)
    all_frame = all_frame.sort_values(["region", "timestamp_kst"]).reset_index(drop=True)
    full_path = processed_dir / f"kma_asos_hourly_regions_{year}.parquet"
    all_frame.to_parquet(full_path, index=False)

    feature_columns = [
        "timestamp_kst",
        "region",
        "region_slug",
        "station_id",
        "station_name",
        "WD",
        "WS",
        "wind_u",
        "wind_v",
        "wind_speed_ms",
        "wind_dir_deg",
        "wind_dir_sin",
        "wind_dir_cos",
        "TA",
        "HM",
        "RN",
    ]
    features = all_frame[[column for column in feature_columns if column in all_frame.columns]].copy()
    features_path = processed_dir / f"kma_asos_hourly_region_features_{year}.parquet"
    features.to_parquet(features_path, index=False)

    manifest = pd.DataFrame(manifest_rows)
    manifest_path = processed_dir / f"kma_asos_hourly_regions_{year}_manifest.csv"
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")

    expected_rows = sum(calendar.monthrange(year, month)[1] * 24 for month in range(1, 13)) * len(REGION_STATIONS)
    summary = {
        "source": "KMA APIHub kma_sfctm3.php",
        "year": year,
        "regions": REGION_STATIONS,
        "rows": int(len(all_frame)),
        "expected_rows": int(expected_rows),
        "missing_rows_vs_expected": int(expected_rows - len(all_frame)),
        "wind_direction_non_null": int(all_frame["WD"].notna().sum()),
        "wind_speed_non_null": int(all_frame["WS"].notna().sum()),
        "full_parquet": str(full_path),
        "features_parquet": str(features_path),
        "manifest_csv": str(manifest_path),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    summary_path = processed_dir / f"kma_asos_hourly_regions_{year}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    args = parse_args()
    auth_key = load_env_key(args.env_file)
    windows = month_windows(args.year)

    all_frames: list[pd.DataFrame] = []
    manifest_rows: list[dict] = []
    for station in REGION_STATIONS:
        frames, rows = collect_station(
            auth_key=auth_key,
            output_root=args.output_root,
            station=station,
            windows=windows,
            timeout_seconds=args.timeout_seconds,
            retries=args.retries,
            sleep_seconds=args.sleep_seconds,
            overwrite=args.overwrite,
        )
        all_frames.extend(frames)
        manifest_rows.extend(rows)

    write_outputs(args.output_root, args.year, all_frames, manifest_rows)


if __name__ == "__main__":
    main()
