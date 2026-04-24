from __future__ import annotations

from pathlib import Path

import torch


def save_checkpoint(
    checkpoint_dir: str | Path,
    run_name: str,
    epoch: int,
    model,
    optimizer,
    metrics: dict,
    is_best: bool,
) -> None:
    directory = Path(checkpoint_dir) / run_name
    directory.mkdir(parents=True, exist_ok=True)

    payload = {
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "metrics": metrics,
    }

    torch.save(payload, directory / "latest.pt")
    torch.save(payload, directory / f"epoch_{epoch:03d}.pt")

    if is_best:
        torch.save(payload, directory / "best.pt")


def load_latest_checkpoint(checkpoint_dir: str | Path, run_name: str):
    latest_path = Path(checkpoint_dir) / run_name / "latest.pt"
    if not latest_path.exists():
        return None
    return torch.load(latest_path, map_location="cpu")
