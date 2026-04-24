from __future__ import annotations

import math

import torch


def mae(predictions: torch.Tensor, targets: torch.Tensor) -> float:
    return torch.mean(torch.abs(predictions - targets)).item()


def rmse(predictions: torch.Tensor, targets: torch.Tensor) -> float:
    mse = torch.mean((predictions - targets) ** 2).item()
    return math.sqrt(mse)


def mape(predictions: torch.Tensor, targets: torch.Tensor, epsilon: float = 1e-6) -> float:
    denominator = torch.clamp(torch.abs(targets), min=epsilon)
    value = torch.mean(torch.abs((targets - predictions) / denominator)).item()
    return value * 100.0
