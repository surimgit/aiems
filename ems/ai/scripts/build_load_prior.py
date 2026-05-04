from __future__ import annotations

import argparse
import calendar
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import yaml


MONTH_COLUMNS = {f"{month}월": month for month in range(1, 13)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a statistical hourly load prior from public usage data.")
    parser.add_argument("--config", default="ems/ai/configs/ops/load_prior_example.yaml")
    parser.add_argument("--output", default=None, help="Override output.csv_path")
    return parser.parse_args()


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def parse_time(value: str, timezone_name: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone_name))
    return parsed


def target_times(config: dict[str, Any]) -> list[datetime]:
    site = config["site"]
    targets = config["targets"]
    start = parse_time(targets["start_time"], site.get("timezone", "Asia/Seoul"))
    periods = int(targets.get("periods", 24))
    step = timedelta(hours=float(targets.get("frequency_hours", 1)))
    return [start + step * index for index in range(periods)]


def city_usage_file(data_root: Path, year: int) -> Path:
    directory = data_root / "raw" / "load" / "kepco_city_usage" / "downloads"
    matches = sorted(directory.glob(f"*{year}12.xlsx"))
    if not matches:
        raise FileNotFoundError(f"No KEPCO city usage xlsx found for year {year}: {directory}")
    return matches[-1]


def read_monthly_usage(config: dict[str, Any]) -> tuple[dict[int, float], dict[str, Any]]:
    site = config["site"]
    baseline = config["load_baseline"]
    data_root = Path(baseline["data_root"])
    year = int(baseline["year"])
    dimension = baseline.get("dimension", "industry")
    path = city_usage_file(data_root, year)

    if dimension == "industry":
        sheet = "용도업종별"
        key_column = "업종별"
        key_value = baseline.get("industry_type")
    elif dimension == "contract":
        sheet = "계약종별"
        key_column = "계약종별"
        key_value = baseline.get("contract_type")
    else:
        raise ValueError("load_baseline.dimension must be industry or contract")
    if not key_value:
        raise ValueError(f"Missing key value for dimension {dimension}")

    frame = pd.read_excel(path, sheet_name=sheet, header=2)
    filtered = frame[
        (frame["연도"].astype(str) == str(year))
        & (frame["시도"].astype(str) == str(site["region"]))
        & (frame["시군구"].astype(str) == str(site["city"]))
        & (frame[key_column].astype(str).str.replace(r"\s+", "", regex=True) == str(key_value).replace(" ", ""))
    ]
    if filtered.empty:
        available = frame[
            (frame["시도"].astype(str) == str(site["region"])) & (frame["시군구"].astype(str) == str(site["city"]))
        ][key_column].dropna().astype(str).head(30).to_list()
        raise ValueError(f"No monthly usage row matched {key_column}={key_value}. Available examples: {available}")

    row = filtered.iloc[0]
    monthly = {month: float(row[column]) for column, month in MONTH_COLUMNS.items() if column in row and pd.notna(row[column])}
    return monthly, {
        "path": str(path),
        "sheet": sheet,
        "dimension": dimension,
        "key_column": key_column,
        "key_value": key_value,
        "year": year,
        "region": site["region"],
        "city": site["city"],
    }


def read_national_hourly_profile(data_root: Path) -> pd.DataFrame:
    directory = data_root / "raw" / "load" / "kpx_national_demand" / "downloads"
    matches = sorted(directory.glob("*.csv"))
    if not matches:
        raise FileNotFoundError(f"No KPX national demand CSV found: {directory}")
    frame = pd.read_csv(matches[-1], encoding="cp949")
    date_column = frame.columns[0]
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        date = pd.to_datetime(row[date_column], errors="coerce")
        if pd.isna(date):
            continue
        values = [float(row[column]) for column in frame.columns[1:25]]
        daily_mean = sum(values) / len(values)
        if daily_mean <= 0:
            continue
        for index, value in enumerate(values):
            hour = index
            records.append(
                {
                    "month": int(date.month),
                    "is_weekend": bool(date.weekday() >= 5),
                    "hour": hour,
                    "hourly_weight": value / daily_mean,
                }
            )
    profile = pd.DataFrame(records)
    grouped = profile.groupby(["month", "is_weekend", "hour"], as_index=False)["hourly_weight"].mean()
    return grouped


def hourly_weight(profile: pd.DataFrame, timestamp: datetime) -> float:
    subset = profile[
        (profile["month"] == timestamp.month)
        & (profile["is_weekend"] == (timestamp.weekday() >= 5))
        & (profile["hour"] == timestamp.hour)
    ]
    if subset.empty:
        subset = profile[(profile["month"] == timestamp.month) & (profile["hour"] == timestamp.hour)]
    if subset.empty:
        subset = profile[profile["hour"] == timestamp.hour]
    if subset.empty:
        return 1.0
    return float(subset["hourly_weight"].mean())


def load_profile(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    profile_path = Path(path)
    if not profile_path.exists():
        raise FileNotFoundError(f"site profile not found: {profile_path}")
    return json.loads(profile_path.read_text(encoding="utf-8"))


def profile_weight(profile: dict[str, Any] | None, timestamp: datetime) -> tuple[float, list[str]]:
    if not profile:
        return 1.0, []
    features = profile.get("forecast_context_features", {})
    weight = 1.0
    reasons: list[str] = []
    if timestamp.weekday() < 5:
        bias = float(features.get("weekday_load_bias", 0.0))
        weight *= 1.0 + bias
        if bias:
            reasons.append(f"weekday_bias={bias:+.2f}")
    else:
        bias = float(features.get("weekend_load_bias", 0.0))
        weight *= 1.0 + bias
        if bias:
            reasons.append(f"weekend_bias={bias:+.2f}")
    if timestamp.hour < 6 or timestamp.hour >= 22:
        bias = float(features.get("night_load_bias", 0.0))
        weight *= 1.0 + bias
        if bias:
            reasons.append(f"night_bias={bias:+.2f}")
    if timestamp.month in (6, 7, 8, 9):
        bias = float(features.get("summer_load_bias", 0.0))
        weight *= 1.0 + bias
        if bias:
            reasons.append(f"summer_bias={bias:+.2f}")
    return max(0.2, weight), reasons


def load_holidays(config: dict[str, Any]) -> set[str]:
    calendar_config = config.get("calendar", {})
    if not bool(calendar_config.get("enabled", False)):
        return set()
    path = calendar_config.get("special_days_path")
    if not path or not Path(path).exists():
        return set()
    frame = pd.read_csv(path)
    if "date" not in frame.columns:
        return set()
    if "is_holiday" in frame.columns:
        frame = frame[frame["is_holiday"].astype(bool)]
    return set(pd.to_datetime(frame["date"], errors="coerce").dropna().dt.strftime("%Y-%m-%d"))


def calendar_weight(config: dict[str, Any], holidays: set[str], timestamp: datetime) -> tuple[float, str | None]:
    if timestamp.strftime("%Y-%m-%d") in holidays:
        return float(config.get("calendar", {}).get("holiday_weight", 0.85)), "holiday"
    return 1.0, None


def weather_weight(config: dict[str, Any], timestamp: datetime) -> tuple[float, str | None]:
    weather = config.get("weather_adjustment", {})
    if not bool(weather.get("enabled", False)):
        return 1.0, None
    temperature = weather.get("temperature_c")
    if temperature is None:
        return 1.0, None
    temp = float(temperature)
    max_weight = float(weather.get("max_weight", 1.25))
    cooling_threshold = float(weather.get("cooling_threshold_c", 26.0))
    heating_threshold = float(weather.get("heating_threshold_c", 5.0))
    if temp >= cooling_threshold:
        weight = min(max_weight, 1.0 + (temp - cooling_threshold) * 0.02)
        return weight, "cooling_adjustment"
    if temp <= heating_threshold:
        weight = min(max_weight, 1.0 + (heating_threshold - temp) * 0.015)
        return weight, "heating_adjustment"
    return 1.0, None


def apply_safety_margin(config: dict[str, Any], predicted_load_kw: float) -> tuple[float, float, str | None]:
    safety = config.get("safety_margin", {})
    if not bool(safety.get("enabled", False)):
        return predicted_load_kw, 0.0, None
    reserve_ratio = float(safety.get("reserve_ratio", 0.15))
    min_reserve_kw = float(safety.get("min_reserve_kw", 0.0))
    reserve_kw = max(predicted_load_kw * reserve_ratio, min_reserve_kw)
    safe_load_kw = predicted_load_kw + reserve_kw
    max_safe_load_kw = safety.get("max_safe_load_kw")
    reason = f"safety_margin={reserve_ratio:.2f},min_reserve_kw={min_reserve_kw:.2f}"
    if max_safe_load_kw is not None:
        cap = float(max_safe_load_kw)
        if safe_load_kw > cap:
            safe_load_kw = cap
            reserve_kw = max(0.0, safe_load_kw - predicted_load_kw)
            reason += f",cap={cap:.2f}"
    return safe_load_kw, reserve_kw, reason


def build_prior(config: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    monthly_kwh, source = read_monthly_usage(config)
    baseline = config["load_baseline"]
    data_root = Path(baseline["data_root"])
    demand_profile = read_national_hourly_profile(data_root)
    site_profile = load_profile(config.get("profile", {}).get("path"))
    holidays = load_holidays(config)
    scale_factor = float(baseline.get("scale_factor", 1.0))
    min_load_kw = float(baseline.get("min_load_kw", 0.0))

    rows: list[dict[str, Any]] = []
    for timestamp in target_times(config):
        month_kwh = monthly_kwh.get(timestamp.month)
        if month_kwh is None:
            raise ValueError(f"Missing monthly kWh for month {timestamp.month}")
        days = calendar.monthrange(timestamp.year, timestamp.month)[1]
        base_load_kw = (month_kwh * scale_factor) / days / 24.0
        h_weight = hourly_weight(demand_profile, timestamp)
        p_weight, p_reasons = profile_weight(site_profile, timestamp)
        c_weight, c_reason = calendar_weight(config, holidays, timestamp)
        w_weight, w_reason = weather_weight(config, timestamp)
        predicted = max(min_load_kw, base_load_kw * h_weight * p_weight * c_weight * w_weight)
        safe_load_kw, reserve_kw, safety_reason = apply_safety_margin(config, predicted)
        reasons = [reason for reason in [c_reason, w_reason, *p_reasons] if reason]
        if safety_reason:
            reasons.append(safety_reason)
        rows.append(
            {
                "timestamp": timestamp.isoformat(),
                "site_id": config["site"].get("site_id"),
                "region": config["site"].get("region"),
                "city": config["site"].get("city"),
                "dimension": source["dimension"],
                "usage_key": source["key_value"],
                "monthly_kwh": month_kwh,
                "scale_factor": scale_factor,
                "base_load_kw": base_load_kw,
                "hourly_profile_weight": h_weight,
                "calendar_weight": c_weight,
                "weather_weight": w_weight,
                "profile_weight": p_weight,
                "predicted_load_kw": predicted,
                "safety_reserve_kw": reserve_kw,
                "safe_predicted_load_kw": safe_load_kw,
                "reason": ";".join(reasons) if reasons else "baseline",
                "profile_site_type": site_profile.get("site_type") if site_profile else None,
                "critical_load_level": (
                    site_profile.get("forecast_context_features", {}).get("critical_load_level") if site_profile else None
                ),
            }
        )
    manifest = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": source,
        "rows": len(rows),
        "profile_path": config.get("profile", {}).get("path"),
        "target_start": rows[0]["timestamp"] if rows else None,
        "target_end": rows[-1]["timestamp"] if rows else None,
    }
    return pd.DataFrame(rows), manifest


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    frame, manifest = build_prior(config)
    csv_path = Path(args.output or config.get("output", {}).get("csv_path", "ems/ai/outputs/load_prior/load_prior.csv"))
    manifest_path = Path(config.get("output", {}).get("manifest_path", str(csv_path.with_suffix(".manifest.json"))))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "csv_path": str(csv_path), "manifest_path": str(manifest_path), **manifest}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
