from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    import torch
    from torch.utils.data import Dataset
else:
    Dataset = object


def load_dataframe(path: str | Path, file_format: str) -> pd.DataFrame:
    source = Path(path)
    if file_format == "csv":
        return pd.read_csv(source)
    if file_format == "parquet":
        return pd.read_parquet(source)
    raise ValueError(f"Unsupported file format: {file_format}")


class TabularDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, feature_columns: list[str], target_column: str) -> None:
        try:
            import torch
        except ImportError as error:
            raise RuntimeError("PyTorch is required for TabularDataset. LightGBM paths do not require it.") from error

        missing = [column for column in feature_columns + [target_column] if column not in frame.columns]
        if missing:
            raise ValueError(f"Missing columns in dataset: {missing}")

        self.features = torch.tensor(frame[feature_columns].to_numpy(), dtype=torch.float32)
        self.targets = torch.tensor(frame[target_column].to_numpy(), dtype=torch.float32).view(-1, 1)

    def __len__(self) -> int:
        return len(self.features)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.features[index], self.targets[index]
