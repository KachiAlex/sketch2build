"""Sketch-to-Graph Vision Encoder model.

Fine-tunes a CLIP/SigLIP vision model to understand architectural sketches
and extract structured room graphs (room types, adjacency, dimensions).
"""

import torch
import torch.nn as nn
from transformers import CLIPVisionModel, CLIPProcessor, CLIPVisionConfig
from typing import Any


class RoomGraphHead(nn.Module):
    """Detection head that predicts room types, adjacency, and bounding boxes from image features."""

    def __init__(self, hidden_dim: int = 768, num_room_types: int = 12, max_rooms: int = 20):
        super().__init__()
        self.max_rooms = max_rooms
        self.num_room_types = num_room_types

        # Room type classifier
        self.room_type_proj = nn.Linear(hidden_dim, num_room_types)

        # Room presence classifier (which of max_rooms are present)
        self.room_presence = nn.Linear(hidden_dim, max_rooms)

        # Bounding box regressor (x, y, w, h) for each room
        self.bbox_regressor = nn.Linear(hidden_dim, max_rooms * 4)

        # Adjacency matrix predictor (max_rooms x max_rooms)
        self.adjacency_proj = nn.Linear(hidden_dim, max_rooms * max_rooms)

    def forward(self, image_features: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            image_features: (batch, hidden_dim) from CLIP vision encoder

        Returns:
            Dict with logits for room types, presence, bboxes, adjacency
        """
        batch_size = image_features.size(0)

        room_type_logits = self.room_type_proj(image_features)  # (B, num_room_types)
        room_presence_logits = self.room_presence(image_features)  # (B, max_rooms)
        bbox_logits = self.bbox_regressor(image_features).view(batch_size, self.max_rooms, 4)
        adjacency_logits = self.adjacency_proj(image_features).view(
            batch_size, self.max_rooms, self.max_rooms
        )

        return {
            "room_type_logits": room_type_logits,
            "room_presence_logits": room_presence_logits,
            "bbox_logits": bbox_logits,
            "adjacency_logits": adjacency_logits,
        }


class SketchEncoderModel(nn.Module):
    """Complete model: CLIP vision encoder + custom room graph head."""

    ROOM_TYPES = [
        "living",
        "kitchen",
        "bedroom",
        "bathroom",
        "dining",
        "hallway",
        "entrance",
        "balcony",
        "storage",
        "garage",
        "office",
        "utility",
    ]

    def __init__(self, pretrained_model: str = "openai/clip-vit-large-patch14", freeze_backbone: bool = False):
        super().__init__()
        self.vision_model = CLIPVisionModel.from_pretrained(pretrained_model)
        self.hidden_dim = self.vision_model.config.hidden_size

        if freeze_backbone:
            for param in self.vision_model.parameters():
                param.requires_grad = False

        self.graph_head = RoomGraphHead(
            hidden_dim=self.hidden_dim,
            num_room_types=len(self.ROOM_TYPES),
            max_rooms=20,
        )

    def forward(self, pixel_values: torch.Tensor) -> dict[str, torch.Tensor]:
        vision_outputs = self.vision_model(pixel_values=pixel_values)
        # Use pooled output (CLS token) for global scene understanding
        image_features = vision_outputs.pooler_output  # (batch, hidden_dim)
        return self.graph_head(image_features)

    def predict(self, pixel_values: torch.Tensor) -> list[dict[str, Any]]:
        """Inference: return structured room graphs for batch of images."""
        self.eval()
        with torch.no_grad():
            outputs = self.forward(pixel_values)

        batch_size = pixel_values.size(0)
        results = []

        for b in range(batch_size):
            presence = torch.sigmoid(outputs["room_presence_logits"][b]) > 0.5
            room_indices = presence.nonzero(as_tuple=True)[0].tolist()

            rooms = []
            for idx in room_indices:
                room_type_idx = torch.argmax(outputs["room_type_logits"][b]).item()
                rooms.append({
                    "type": self.ROOM_TYPES[room_type_idx],
                    "bbox": outputs["bbox_logits"][b, idx].tolist(),
                })

            adjacency = torch.sigmoid(outputs["adjacency_logits"][b]) > 0.5
            adjacency_pairs = adjacency.nonzero().tolist()

            results.append({
                "rooms": rooms,
                "adjacency": adjacency_pairs,
            })

        return results
