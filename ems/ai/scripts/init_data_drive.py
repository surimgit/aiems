from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize Google Drive folder layout for EMS AI project data."
    )
    parser.add_argument(
        "--config",
        default="ems/ai/configs/data_sources/google_drive_storage_example.yaml",
        help="Path to YAML config.",
    )
    parser.add_argument(
        "--region",
        default="jeonnam",
        help="Default region slug to create under source folders.",
    )
    parser.add_argument(
        "--station-id",
        default="165",
        help="Default station id used for KMA ASOS folder layout.",
    )
    return parser.parse_args()


def load_config(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_layout(base: Path, region: str, station_id: str, raw_sources: list[str]) -> list[Path]:
    paths: list[Path] = []

    raw_root = base / "raw"
    processed_root = base / "processed"
    artifacts_root = base / "artifacts"

    paths.extend([raw_root, processed_root, artifacts_root])

    for source in raw_sources:
        source_root = raw_root / source
        paths.append(source_root)

    kma_station_root = raw_root / "kma_asos" / region / f"station_{station_id}"
    paths.extend(
        [
            kma_station_root / "metadata",
            kma_station_root / "hourly_raw",
            kma_station_root / "hourly_csv",
        ]
    )

    for source in ["kepco", "west_power", "satellite"]:
        paths.extend(
            [
                raw_root / source / region / "downloads",
                raw_root / source / region / "metadata",
            ]
        )

    return paths


def write_readme(base: Path, region: str, station_id: str) -> None:
    content = f"""# S305 AI Data

이 폴더는 이번 프로젝트 외부 학습 데이터 저장용이다.

기본 지역:
- region: `{region}`
- KMA station_id: `{station_id}`

주요 경로:
- `raw/kma_asos/{region}/station_{station_id}/hourly_raw`
- `raw/kma_asos/{region}/station_{station_id}/hourly_csv`
- `raw/kma_asos/{region}/station_{station_id}/metadata`
- `raw/kepco/{region}/downloads`
- `raw/west_power/{region}/downloads`
- `raw/satellite/{region}/downloads`
- `processed/merged`
- `processed/features`
- `processed/splits`
- `artifacts/manifests`
- `artifacts/exports`
"""
    (base / "README.md").write_text(content, encoding="utf-8")


def write_manifest(base: Path, region: str, station_id: str, config: dict) -> None:
    manifest = {
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "region": region,
        "station_id": station_id,
        "project_folder": config["project_folder"],
        "raw_sources": config["raw_sources"],
        "processed_dirs": config["processed_dirs"],
        "artifact_dirs": config["artifact_dirs"],
    }
    manifest_path = base / "artifacts" / "manifests" / "layout_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    drive_root = Path(config["drive_root"])
    project_root = drive_root / config["project_folder"]

    mkdir(project_root)

    layout_paths = build_layout(
        project_root,
        args.region,
        args.station_id,
        config["raw_sources"],
    )

    for path in layout_paths:
        mkdir(path)

    for name in config["processed_dirs"]:
        mkdir(project_root / "processed" / name)

    for name in config["artifact_dirs"]:
        mkdir(project_root / "artifacts" / name)

    write_readme(project_root, args.region, args.station_id)
    write_manifest(project_root, args.region, args.station_id, config)

    print(f"Initialized data root: {project_root}")
    print("You can now point collection configs to this root.")


if __name__ == "__main__":
    main()
