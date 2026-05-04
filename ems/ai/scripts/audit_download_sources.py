from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from astral import Observer
from astral.sun import elevation


DOWNLOADS = Path(r"C:\Users\SSAFY\Downloads")
DEFAULT_OUTPUT = Path("ems/ai/outputs/download_source_audit.json")
JEONNAM_SOLAR_CSV = DOWNLOADS / "한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231.csv"
JEONNAM_SOLAR_CSV_COPY = DOWNLOADS / "한국전력거래소_지역별 시간별 태양광 및 풍력 발전량_20251231 (1).csv"
GRID_XLSX = DOWNLOADS / "동네예보지점좌표(위경도)_202601.xlsx"
CONTRACT_1H_XLSX = DOWNLOADS / "(제공) 2501_06_계약종별-법정동별 전력데이터.xlsx"
CONTRACT_2H_XLSX = DOWNLOADS / "(제공) 2507_12_계약종별-법정동별 전력데이터.xlsx"
NATIONAL_DEMAND_CSV = DOWNLOADS / "한국전력거래소_시간별 전국 전력수요량_20251231.csv"
WEST_REC_CSV = DOWNLOADS / "한국서부발전(주)_REC거래현황_20250701.csv"
WEST_SOLAR_CSV = DOWNLOADS / "한국서부발전(주)_태양광 발전 현황_20230630.csv"
CITY_POWER_DIR = DOWNLOADS / "시군구별전력사용량"
GDRIVE_KPX_NORMALIZED = Path(r"G:\내 드라이브\s305-ai-data\raw\kepco\jeonnam\normalized\kepco_jeonnam_hourly.csv")


def file_sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_any(path: Path) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None
    for encoding in ("cp949", "utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding), encoding
        except UnicodeDecodeError as error:
            last_error = error
    if last_error:
        raise last_error
    return pd.read_csv(path), "default"


def file_info(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "bytes": path.stat().st_size if path.exists() and path.is_file() else None,
        "sha256": file_sha256(path),
    }


def dataframe_summary(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(frame)),
        "columns": list(map(str, frame.columns)),
        "null_cells": int(frame.isna().sum().sum()),
    }


def audit_kpx_solar(path: Path) -> dict[str, Any]:
    frame, encoding = read_csv_any(path)
    renamed = frame.rename(
        columns={
            "거래일": "trade_date",
            "거래시간": "hour_ending",
            "지역": "region",
            "연료원": "fuel_type",
            "전력거래량(MWh)": "generation_mwh",
        }
    )
    required = {"trade_date", "hour_ending", "region", "fuel_type", "generation_mwh"}
    missing = sorted(required - set(renamed.columns))
    if missing:
        return {"file": file_info(path), "encoding": encoding, "summary": dataframe_summary(frame), "missing": missing}

    solar = renamed[
        (renamed["region"].astype(str).str.strip() == "전라남도")
        & (renamed["fuel_type"].astype(str).str.strip() == "태양광")
    ].copy()
    solar["hour_ending"] = pd.to_numeric(solar["hour_ending"].astype(str).str.replace("시", ""), errors="coerce")
    solar["timestamp"] = pd.to_datetime(solar["trade_date"]) + pd.to_timedelta(solar["hour_ending"], unit="h")
    solar["generation_mwh"] = pd.to_numeric(solar["generation_mwh"], errors="coerce")
    solar["generation_kw"] = solar["generation_mwh"] * 1000.0
    solar = solar[(solar["timestamp"] >= "2025-01-01") & (solar["timestamp"] < "2026-01-01")].copy()

    observer = Observer(latitude=34.8118, longitude=126.3922)
    timezone = ZoneInfo("Asia/Seoul")
    solar["solar_elevation"] = solar["timestamp"].map(
        lambda value: elevation(observer, value.to_pydatetime().replace(tzinfo=timezone))
    )
    solar["date"] = solar["timestamp"].dt.strftime("%Y-%m-%d")
    solar["hour"] = solar["timestamp"].dt.hour

    threshold_payload = {}
    for threshold in (1, 100, 1_000, 10_000, 100_000):
        bad = solar[(solar["solar_elevation"] <= 0) & (solar["generation_kw"] > threshold)]
        threshold_payload[str(threshold)] = {
            "rows": int(len(bad)),
            "days": int(bad["date"].nunique()),
            "total_mwh": float(bad["generation_mwh"].sum()),
        }

    top_bad = (
        solar[(solar["solar_elevation"] <= 0) & (solar["generation_kw"] > 1_000)]
        .groupby("date")
        .agg(
            rows=("generation_kw", "size"),
            total_mwh=("generation_mwh", "sum"),
            max_mwh=("generation_mwh", "max"),
            hours=("hour", lambda values: ",".join(map(str, sorted(values.unique())))),
        )
        .sort_values("total_mwh", ascending=False)
        .head(20)
        .reset_index()
    )

    hourly = (
        solar.groupby("hour")
        .agg(
            mean_mwh=("generation_mwh", "mean"),
            max_mwh=("generation_mwh", "max"),
            rows_gt_1mwh=("generation_mwh", lambda values: int((values > 1).sum())),
        )
        .reset_index()
    )

    return {
        "file": file_info(path),
        "encoding": encoding,
        "summary": dataframe_summary(frame),
        "jeonnam_solar_rows_2025": int(len(solar)),
        "period": {
            "min": solar["timestamp"].min().isoformat() if not solar.empty else None,
            "max": solar["timestamp"].max().isoformat() if not solar.empty else None,
        },
        "night_generation_by_threshold_kw": threshold_payload,
        "top_bad_days_gt_1mw": top_bad.to_dict(orient="records"),
        "hourly_generation_summary": hourly.round(3).to_dict(orient="records"),
    }


def audit_csv_basic(path: Path) -> dict[str, Any]:
    frame, encoding = read_csv_any(path)
    payload = {"file": file_info(path), "encoding": encoding, "summary": dataframe_summary(frame)}
    for column in frame.columns:
        if "일" in str(column) or "date" in str(column).lower() or "time" in str(column).lower():
            sample = frame[column].dropna().astype(str).head(5).tolist()
            payload.setdefault("date_like_samples", {})[str(column)] = sample
    return payload


def audit_xlsx(path: Path) -> dict[str, Any]:
    xls = pd.ExcelFile(path)
    sheets: dict[str, Any] = {}
    for sheet in xls.sheet_names:
        preview = pd.read_excel(path, sheet_name=sheet, nrows=5)
        sheets[sheet] = {
            "preview_rows": int(len(preview)),
            "preview_columns": list(map(str, preview.columns)),
            "preview": preview.astype(str).where(preview.notna(), None).to_dict(orient="records"),
        }
    return {"file": file_info(path), "sheet_names": xls.sheet_names, "sheets": sheets}


def audit_city_power_dir(path: Path) -> dict[str, Any]:
    files = sorted(path.glob("*.xlsx"))
    return {
        "path": str(path),
        "exists": path.exists(),
        "files": [audit_xlsx(file) for file in files],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit downloaded EMS AI source data files.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    payload = {
        "kpx_solar": audit_kpx_solar(JEONNAM_SOLAR_CSV),
        "kpx_solar_copy_same_hash": file_sha256(JEONNAM_SOLAR_CSV) == file_sha256(JEONNAM_SOLAR_CSV_COPY),
        "kpx_solar_copy": file_info(JEONNAM_SOLAR_CSV_COPY),
        "gdrive_normalized": file_info(GDRIVE_KPX_NORMALIZED),
        "national_demand": audit_csv_basic(NATIONAL_DEMAND_CSV),
        "west_rec": audit_csv_basic(WEST_REC_CSV),
        "west_solar": audit_csv_basic(WEST_SOLAR_CSV),
        "grid_points": audit_xlsx(GRID_XLSX),
        "contract_power_2501_06": audit_xlsx(CONTRACT_1H_XLSX),
        "contract_power_2507_12": audit_xlsx(CONTRACT_2H_XLSX),
        "city_power": audit_city_power_dir(CITY_POWER_DIR),
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
