from __future__ import annotations

import json
import logging
from pathlib import Path


def create_logger(log_dir: str | Path, run_name: str) -> logging.Logger:
    directory = Path(log_dir) / run_name
    directory.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"ems.ai.train.{run_name}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(directory / "train.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def append_metrics(log_dir: str | Path, run_name: str, payload: dict) -> None:
    directory = Path(log_dir) / run_name
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "metrics.jsonl").open("a", encoding="utf-8") as file:
        file.write(json.dumps(payload, ensure_ascii=True) + "\n")
