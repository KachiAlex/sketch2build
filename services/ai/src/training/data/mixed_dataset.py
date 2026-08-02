"""Mixed dataset that combines synthetic, RPlan, and CubiCasa5K data.

This allows training on a blend of procedurally generated data and
real-world floor plans for better generalization.
"""

import json
import random
import structlog
from pathlib import Path
from typing import Any, Iterator

import torch
from torch.utils.data import Dataset, ConcatDataset, WeightedRandomSampler
from PIL import Image
from transformers import CLIPProcessor

from src.training.data.dataset import SketchDataset, LayoutDataset

logger = structlog.get_logger()


class MixedSketchDataset(Dataset):
    """Combines multiple sketch datasets with configurable sampling weights."""

    def __init__(
        self,
        datasets: list[SketchDataset],
        weights: list[float] | None = None,
    ):
        self.datasets = datasets
        self.weights = weights or [1.0] * len(datasets)
        self.total_size = sum(len(d) for d in datasets)

        # Create cumulative distribution for weighted sampling
        self.cum_weights = []
        cumulative = 0
        for d, w in zip(datasets, self.weights):
            cumulative += len(d) * w
            self.cum_weights.append(cumulative)
        self.total_weight = cumulative

        logger.info(
            "MixedSketchDataset created",
            num_datasets=len(datasets),
            total_samples=self.total_size,
            weights=self.weights,
        )

    def __len__(self) -> int:
        return self.total_size

    def __getitem__(self, idx: int) -> dict[str, Any]:
        # Weighted random sampling across datasets
        r = random.random() * self.total_weight
        for i, cw in enumerate(self.cum_weights):
            if r <= cw:
                # Pick random sample from this dataset
                dataset_idx = random.randint(0, len(self.datasets[i]) - 1)
                return self.datasets[i][dataset_idx]

        # Fallback
        return self.datasets[0][idx % len(self.datasets[0])]


class MixedLayoutDataset(Dataset):
    """Combines multiple layout datasets with configurable sampling weights."""

    def __init__(
        self,
        datasets: list[LayoutDataset],
        weights: list[float] | None = None,
    ):
        self.datasets = datasets
        self.weights = weights or [1.0] * len(datasets)
        self.total_size = sum(len(d) for d in datasets)

        self.cum_weights = []
        cumulative = 0
        for d, w in zip(datasets, self.weights):
            cumulative += len(d) * w
            self.cum_weights.append(cumulative)
        self.total_weight = cumulative

        logger.info(
            "MixedLayoutDataset created",
            num_datasets=len(datasets),
            total_samples=self.total_size,
            weights=self.weights,
        )

    def __len__(self) -> int:
        return self.total_size

    def __getitem__(self, idx: int) -> dict[str, Any]:
        r = random.random() * self.total_weight
        for i, cw in enumerate(self.cum_weights):
            if r <= cw:
                dataset_idx = random.randint(0, len(self.datasets[i]) - 1)
                return self.datasets[i][dataset_idx]
        return self.datasets[0][idx % len(self.datasets[0])]


def create_mixed_datasets(
    synthetic_dir: str,
    rplan_dir: str | None = None,
    cubicasa_dir: str | None = None,
    processor: CLIPProcessor | None = None,
    split: str = "train",
    weights: dict[str, float] | None = None,
    image_size: int = 256,
    max_rooms: int = 20,
) -> tuple[MixedSketchDataset, MixedLayoutDataset]:
    """
    Create mixed datasets combining synthetic, RPlan, and CubiCasa5K data.

    Args:
        synthetic_dir: Path to synthetic dataset directory
        rplan_dir: Path to RPlan dataset directory (optional)
        cubicasa_dir: Path to CubiCasa5K dataset directory (optional)
        processor: CLIP processor for vision dataset
        split: "train", "val", or "test"
        weights: Dict of dataset_name -> weight. Defaults to equal weighting.
        image_size: Image size for layout dataset
        max_rooms: Maximum number of rooms per plan

    Returns:
        Tuple of (sketch_dataset, layout_dataset)
    """
    default_weights = {"synthetic": 0.5, "rplan": 0.3, "cubicasa": 0.2}
    weights = weights or default_weights

    # Build sketch datasets
    sketch_datasets = []
    sketch_weights = []

    if Path(synthetic_dir).exists():
        sketch_datasets.append(SketchDataset(
            metadata_path=Path(synthetic_dir) / "metadata.json",
            image_dir=synthetic_dir,
            processor=processor,
            split=split,
            max_rooms=max_rooms,
        ))
        sketch_weights.append(weights.get("synthetic", 0.5))

    if rplan_dir and Path(rplan_dir).exists():
        sketch_datasets.append(SketchDataset(
            metadata_path=Path(rplan_dir) / "metadata.json",
            image_dir=rplan_dir,
            processor=processor,
            split=split,
            max_rooms=max_rooms,
        ))
        sketch_weights.append(weights.get("rplan", 0.3))

    if cubicasa_dir and Path(cubicasa_dir).exists():
        sketch_datasets.append(SketchDataset(
            metadata_path=Path(cubicasa_dir) / "metadata.json",
            image_dir=cubicasa_dir,
            processor=processor,
            split=split,
            max_rooms=max_rooms,
        ))
        sketch_weights.append(weights.get("cubicasa", 0.2))

    if not sketch_datasets:
        raise ValueError("No datasets found. Please provide at least one valid dataset directory.")

    sketch_dataset = MixedSketchDataset(sketch_datasets, sketch_weights)

    # Build layout datasets
    layout_datasets = []
    layout_weights = []

    if Path(synthetic_dir).exists():
        layout_datasets.append(LayoutDataset(
            metadata_path=Path(synthetic_dir) / "metadata.json",
            image_dir=synthetic_dir,
            split=split,
            image_size=image_size,
            max_rooms=max_rooms,
        ))
        layout_weights.append(weights.get("synthetic", 0.5))

    if rplan_dir and Path(rplan_dir).exists():
        layout_datasets.append(LayoutDataset(
            metadata_path=Path(rplan_dir) / "metadata.json",
            image_dir=rplan_dir,
            split=split,
            image_size=image_size,
            max_rooms=max_rooms,
        ))
        layout_weights.append(weights.get("rplan", 0.3))

    if cubicasa_dir and Path(cubicasa_dir).exists():
        layout_datasets.append(LayoutDataset(
            metadata_path=Path(cubicasa_dir) / "metadata.json",
            image_dir=cubicasa_dir,
            split=split,
            image_size=image_size,
            max_rooms=max_rooms,
        ))
        layout_weights.append(weights.get("cubicasa", 0.2))

    layout_dataset = MixedLayoutDataset(layout_datasets, layout_weights)

    return sketch_dataset, layout_dataset
