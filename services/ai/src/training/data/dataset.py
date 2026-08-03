"""PyTorch Dataset classes for training."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import Dataset
from PIL import Image
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
    ):
        self.image_dir = Path(image_dir)
        self.processor = processor
        self.max_rooms = max_rooms
        self.split = split

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

        for i, room in enumerate(rooms[:num_rooms]):
            room_types[i] = self.room_type_to_idx.get(room["type"], 0)
            bboxes[i] = torch.tensor([room["x"], room["y"], room["w"], room["d"]], dtype=torch.float32)
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
    ):
        self.image_dir = Path(image_dir)
        self.image_size = image_size
        self.max_rooms = max_rooms
        self.split = split

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

        # Normalize to [-1, 1]
        image_tensor = torch.from_numpy(np.array(image)).permute(2, 0, 1).float() / 127.5 - 1.0

        # Build graph conditioning
        rooms = item.get("rooms", [])
        num_rooms = min(len(rooms), self.max_rooms)

        room_types = torch.zeros(self.max_rooms, dtype=torch.long)
        bboxes = torch.zeros(self.max_rooms, 4, dtype=torch.float32)
        mask = torch.zeros(self.max_rooms, dtype=torch.bool)
        adjacency = torch.zeros(self.max_rooms, self.max_rooms, dtype=torch.float32)

        for i, room in enumerate(rooms[:num_rooms]):
            room_types[i] = self.room_type_to_idx.get(room["type"], 0)
            bboxes[i] = torch.tensor([room["x"], room["y"], room["w"], room["d"]], dtype=torch.float32)
            mask[i] = True

        for i, j in item.get("adjacency", []):
            if i < self.max_rooms and j < self.max_rooms:
                adjacency[i, j] = 1.0
                adjacency[j, i] = 1.0

        return {
            "image": image_tensor,
            "rooms": [{"type": r["type"], "type_idx": self.room_type_to_idx.get(r["type"], 0),
                        "bbox": [r["x"], r["y"], r["w"], r["d"]]} for r in rooms[:num_rooms]],
            "adjacency": item.get("adjacency", []),
            "image_id": item["id"],
        }
