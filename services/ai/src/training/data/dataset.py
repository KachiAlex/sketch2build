"""PyTorch Dataset classes for training."""

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image, ImageFilter
from transformers import CLIPProcessor


class SketchDataset(Dataset):
    """Dataset for sketch-to-graph training (vision encoder)."""

    ROOM_TYPES = [
        "living", "kitchen", "bedroom", "bathroom", "dining",
        "hallway", "entrance", "balcony", "storage", "garage",
        "office", "utility",
    ]

    def __init__(
        self,
        metadata_path: str,
        image_dir: str,
        processor: CLIPProcessor,
        split: str = "train",
        max_rooms: int = 20,
        augment: bool = True,
    ):
        self.image_dir = Path(image_dir)
        self.processor = processor
        self.max_rooms = max_rooms
        self.split = split
        self.augment = augment and split == "train"

        with open(metadata_path) as f:
            all_data = json.load(f)

        # Simple split: 80% train, 10% val, 10% test
        n = len(all_data)
        if split == "train":
            self.data = all_data[: int(n * 0.8)]
        elif split == "val":
            self.data = all_data[int(n * 0.8) : int(n * 0.9)]
        else:
            self.data = all_data[int(n * 0.9) :]

        self.room_type_to_idx = {rt: i for i, rt in enumerate(self.ROOM_TYPES)}

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.data[idx]

        # Load sketch image
        image_path = self.image_dir / item["sketch"]
        image = Image.open(image_path).convert("RGB")

        # Data augmentation for training
        if self.augment:
            image = self._augment_image(image)

        # Process with CLIP processor
        inputs = self.processor(images=image, return_tensors="pt")
        pixel_values = inputs["pixel_values"].squeeze(0)

        # Build room graph tensors
        rooms = item.get("rooms", [])
        num_rooms = min(len(rooms), self.max_rooms)

        room_types = torch.full((self.max_rooms,), -1, dtype=torch.long)  # -1 = padding
        bboxes = torch.zeros(self.max_rooms, 4, dtype=torch.float32)
        mask = torch.zeros(self.max_rooms, dtype=torch.bool)
        adjacency = torch.zeros(self.max_rooms, self.max_rooms, dtype=torch.float32)

        plot_w = item.get("width", 20.0)
        plot_d = item.get("depth", 20.0)
        for i, room in enumerate(rooms[:num_rooms]):
            room_types[i] = self.room_type_to_idx.get(room["type"], 0)
            bboxes[i] = torch.tensor([
                room["x"] / plot_w,
                room["y"] / plot_d,
                room["w"] / plot_w,
                room["d"] / plot_d,
            ], dtype=torch.float32)
            mask[i] = True

        for i, j in item.get("adjacency", []):
            if i < self.max_rooms and j < self.max_rooms:
                adjacency[i, j] = 1.0
                adjacency[j, i] = 1.0

        # Valid/invalid label for contrastive learning
        is_valid = torch.tensor(1.0 if item.get("valid", True) else 0.0, dtype=torch.float32)

        return {
            "pixel_values": pixel_values,
            "room_types": room_types,
            "bboxes": bboxes,
            "mask": mask,
            "adjacency": adjacency,
            "is_valid": is_valid,
            "image_id": item["id"],
        }

    def _augment_image(self, image: Image.Image) -> Image.Image:
        """Apply random augmentations to sketch image."""
        # Random horizontal flip
        if random.random() < 0.5:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
        # Random vertical flip (less common for floor plans)
        if random.random() < 0.3:
            image = image.transpose(Image.FLIP_TOP_BOTTOM)
        # Random rotation (small angles)
        if random.random() < 0.3:
            angle = random.uniform(-5, 5)
            image = image.rotate(angle, fillcolor="white")
        # Random Gaussian blur
        if random.random() < 0.2:
            radius = random.uniform(0.5, 1.5)
            image = image.filter(ImageFilter.GaussianBlur(radius=radius))
        # Random brightness/contrast jitter
        if random.random() < 0.3:
            arr = np.array(image).astype(np.float32)
            brightness = random.uniform(0.8, 1.2)
            arr = np.clip(arr * brightness, 0, 255).astype(np.uint8)
            image = Image.fromarray(arr)
        return image


class LayoutDataset(Dataset):
    """Dataset for layout diffusion model training."""

    ROOM_TYPES = [
        "living", "kitchen", "bedroom", "bathroom", "dining",
        "hallway", "entrance", "balcony", "storage", "garage",
        "office", "utility",
    ]

    def __init__(
        self,
        metadata_path: str,
        image_dir: str,
        split: str = "train",
        image_size: int = 256,
        max_rooms: int = 20,
        augment: bool = True,
    ):
        self.image_dir = Path(image_dir)
        self.image_size = image_size
        self.max_rooms = max_rooms
        self.split = split
        self.augment = augment and split == "train"

        with open(metadata_path) as f:
            all_data = json.load(f)

        n = len(all_data)
        if split == "train":
            self.data = all_data[: int(n * 0.8)]
        elif split == "val":
            self.data = all_data[int(n * 0.8) : int(n * 0.9)]
        else:
            self.data = all_data[int(n * 0.9) :]

        self.room_type_to_idx = {rt: i for i, rt in enumerate(self.ROOM_TYPES)}

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> dict[str, Any]:
        item = self.data[idx]

        # Load clean floor plan image (target for diffusion)
        image_path = self.image_dir / item["image"]
        image = Image.open(image_path).convert("RGB").resize((self.image_size, self.image_size))

        # Data augmentation for training
        flip_h = False
        if self.augment:
            image, flip_h = self._augment_image(image)

        # Normalize to [-1, 1]
        image_tensor = torch.from_numpy(np.array(image)).permute(2, 0, 1).float() / 127.5 - 1.0

        # Build graph conditioning
        rooms = item.get("rooms", [])
        num_rooms = min(len(rooms), self.max_rooms)

        room_types = torch.zeros(self.max_rooms, dtype=torch.long)
        bboxes = torch.zeros(self.max_rooms, 4, dtype=torch.float32)
        mask = torch.zeros(self.max_rooms, dtype=torch.bool)
        adjacency = torch.zeros(self.max_rooms, self.max_rooms, dtype=torch.float32)

        plot_w = item.get("width", 20.0)
        plot_d = item.get("depth", 20.0)
        for i, room in enumerate(rooms[:num_rooms]):
            room_types[i] = self.room_type_to_idx.get(room["type"], 0)
            bboxes[i] = torch.tensor([
                room["x"] / plot_w,
                room["y"] / plot_d,
                room["w"] / plot_w,
                room["d"] / plot_d,
            ], dtype=torch.float32)
            mask[i] = True

        for i, j in item.get("adjacency", []):
            if i < self.max_rooms and j < self.max_rooms:
                adjacency[i, j] = 1.0
                adjacency[j, i] = 1.0

        return {
            "image": image_tensor,
            "rooms": [{"type": r["type"], "type_idx": self.room_type_to_idx.get(r["type"], 0),
                        "bbox": [r["x"] / plot_w, r["y"] / plot_d, r["w"] / plot_w, r["d"] / plot_d]} for r in rooms[:num_rooms]],
            "adjacency": item.get("adjacency", []),
            "image_id": item["id"],
            "num_stories": item.get("num_stories", 1),
            "region": item.get("region", "generic"),
            "style": item.get("style", "modern"),
        }

    def _augment_image(self, image: Image.Image) -> tuple[Image.Image, bool]:
        """Apply random augmentations. Returns (image, was_flipped_h)."""
        flip_h = False
        if random.random() < 0.5:
            image = image.transpose(Image.FLIP_LEFT_RIGHT)
            flip_h = True
        if random.random() < 0.2:
            arr = np.array(image).astype(np.float32)
            noise = np.random.normal(0, 5, arr.shape).astype(np.float32)
            arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
            image = Image.fromarray(arr)
        return image, flip_h
