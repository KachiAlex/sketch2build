"""Sketch-to-Graph Vision Encoder model.

Fine-tunes a CLIP vision model to understand architectural sketches
and extract structured room graphs (room types, adjacency, dimensions).

Uses spatial patch tokens (not just pooled CLS) for per-room type prediction.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import CLIPVisionModel, CLIPProcessor
from typing import Any


class RoomQueryEmbedding(nn.Module):
    """Learnable query embeddings for detecting up to max_rooms rooms."""

    def __init__(self, hidden_dim: int, max_rooms: int):
        super().__init__()
        self.queries = nn.Parameter(torch.randn(max_rooms, hidden_dim) * 0.02)
        self.max_rooms = max_rooms

    def forward(self) -> torch.Tensor:
        return self.queries


class RoomGraphHead(nn.Module):
    """Detection head using cross-attention between spatial features and room queries.

    Each room query attends to patch-level features to predict:
    - Whether that room slot is present
    - What type the room is (per-slot, not global)
    - Bounding box coordinates (per-slot)
    """

    def __init__(self, hidden_dim: int = 768, num_room_types: int = 12, max_rooms: int = 20, num_heads: int = 8):
        super().__init__()
        self.max_rooms = max_rooms
        self.num_room_types = num_room_types
        self.hidden_dim = hidden_dim

        # Learnable room queries (one per detectable room slot)
        self.room_queries = RoomQueryEmbedding(hidden_dim, max_rooms)

        # Cross-attention: room queries attend to patch features
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            batch_first=True,
        )
        self.norm1 = nn.LayerNorm(hidden_dim)

        # Self-attention among room queries (for adjacency modeling)
        self.self_attn = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            batch_first=True,
        )
        self.norm2 = nn.LayerNorm(hidden_dim)

        # FFN
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim * 2),
            nn.GELU(),
            nn.Linear(hidden_dim * 2, hidden_dim),
        )
        self.norm3 = nn.LayerNorm(hidden_dim)

        # Per-room prediction heads
        self.room_presence = nn.Linear(hidden_dim, 1)          # (B, max_rooms, 1)
        self.room_type_proj = nn.Linear(hidden_dim, num_room_types)  # (B, max_rooms, num_types)
        self.bbox_regressor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, 4),  # (x, y, w, h) normalized 0-1
        )

        # Adjacency: pairwise room features → edge logits
        self.adjacency_proj = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, patch_features: torch.Tensor, cls_feature: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            patch_features: (B, num_patches, hidden_dim) spatial features from CLIP
            cls_feature: (B, hidden_dim) pooled CLS token for global context

        Returns:
            Dict with per-room logits for type, presence, bboxes, and adjacency
        """
        batch_size = patch_features.size(0)

        # Expand queries for batch
        queries = self.room_queries().unsqueeze(0).expand(batch_size, -1, -1)  # (B, max_rooms, hidden_dim)

        # Cross-attention: queries → patch features
        attn_out, _ = self.cross_attn(queries, patch_features, patch_features)
        room_features = self.norm1(queries + attn_out)  # (B, max_rooms, hidden_dim)

        # Self-attention among rooms (captures adjacency patterns)
        self_attn_out, _ = self.self_attn(room_features, room_features, room_features)
        room_features = self.norm2(room_features + self_attn_out)

        # FFN
        ffn_out = self.ffn(room_features)
        room_features = self.norm3(room_features + ffn_out)

        # Predictions
        room_presence_logits = self.room_presence(room_features).squeeze(-1)  # (B, max_rooms)
        room_type_logits = self.room_type_proj(room_features)                  # (B, max_rooms, num_types)
        bbox_logits = self.bbox_regressor(room_features)                       # (B, max_rooms, 4)
        bbox_logits = torch.sigmoid(bbox_logits)  # normalize to 0-1

        # Adjacency: pairwise combinations
        # (B, max_rooms, 1, hidden_dim) + (B, 1, max_rooms, hidden_dim) → (B, max_rooms, max_rooms, 2*hidden_dim)
        room_i = room_features.unsqueeze(2)  # (B, max_rooms, 1, hidden_dim)
        room_j = room_features.unsqueeze(1)  # (B, 1, max_rooms, hidden_dim)
        pair_features = torch.cat([room_i, room_j], dim=-1)  # (B, max_rooms, max_rooms, 2*hidden_dim)
        adjacency_logits = self.adjacency_proj(pair_features).squeeze(-1)  # (B, max_rooms, max_rooms)

        return {
            "room_type_logits": room_type_logits,
            "room_presence_logits": room_presence_logits,
            "bbox_logits": bbox_logits,
            "adjacency_logits": adjacency_logits,
            "room_features": room_features,
        }


class SketchEncoderModel(nn.Module):
    """Complete model: CLIP vision encoder + cross-attention room graph head."""

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

    def __init__(
        self,
        pretrained_model: str = "openai/clip-vit-large-patch14",
        freeze_backbone: bool = False,
        max_rooms: int = 20,
    ):
        super().__init__()
        self.vision_model = CLIPVisionModel.from_pretrained(pretrained_model)
        self.hidden_dim = self.vision_model.config.hidden_size
        self.max_rooms = max_rooms

        if freeze_backbone:
            for param in self.vision_model.parameters():
                param.requires_grad = False

        self.graph_head = RoomGraphHead(
            hidden_dim=self.hidden_dim,
            num_room_types=len(self.ROOM_TYPES),
            max_rooms=max_rooms,
        )

    def forward(self, pixel_values: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Forward pass returning per-room predictions.

        Args:
            pixel_values: (B, C, H, W) preprocessed images

        Returns:
            Dict with room_type_logits (B, max_rooms, num_types),
            room_presence_logits (B, max_rooms),
            bbox_logits (B, max_rooms, 4),
            adjacency_logits (B, max_rooms, max_rooms)
        """
        vision_outputs = self.vision_model(pixel_values=pixel_values)

        # Use spatial patch tokens for room detection
        patch_features = vision_outputs.last_hidden_state  # (B, num_patches, hidden_dim)
        cls_feature = vision_outputs.pooler_output         # (B, hidden_dim)

        return self.graph_head(patch_features, cls_feature)

    def compute_loss(
        self,
        outputs: dict[str, torch.Tensor],
        targets: dict[str, torch.Tensor],
    ) -> dict[str, torch.Tensor]:
        """
        Compute multi-task loss: room presence (BCE) + room type (CE) + bbox (L1) + adjacency (BCE).

        Args:
            outputs: Model forward outputs
            targets: Dict with keys:
                - room_presence: (B, max_rooms) float 0/1
                - room_types: (B, max_rooms) long, -1 for padding
                - bboxes: (B, max_rooms, 4) float, normalized 0-1
                - adjacency: (B, max_rooms, max_rooms) float 0/1
                - mask: (B, max_rooms) bool, True = valid room
        """
        mask = targets["mask"].float()  # (B, max_rooms)

        # Presence loss (BCE)
        presence_loss = F.binary_cross_entropy_with_logits(
            outputs["room_presence_logits"], targets["room_presence"], reduction="none"
        )
        presence_loss = (presence_loss * mask).sum() / mask.sum().clamp(min=1)

        # Room type loss (cross-entropy, only for valid rooms)
        valid_rooms = targets["room_types"] >= 0  # (B, max_rooms)
        if valid_rooms.any():
            type_logits = outputs["room_type_logits"][valid_rooms]  # (N_valid, num_types)
            type_targets = targets["room_types"][valid_rooms]       # (N_valid,)
            type_loss = F.cross_entropy(type_logits, type_targets)
        else:
            type_loss = torch.tensor(0.0, device=outputs["room_type_logits"].device)

        # Bbox loss (L1, only for valid rooms)
        bbox_loss = F.l1_loss(
            outputs["bbox_logits"], targets["bboxes"], reduction="none"
        )  # (B, max_rooms, 4)
        bbox_loss = (bbox_loss.mean(dim=-1) * mask).sum() / mask.sum().clamp(min=1)

        # Adjacency loss (BCE, only for valid room pairs)
        adj_mask = mask.unsqueeze(2) * mask.unsqueeze(1)  # (B, max_rooms, max_rooms)
        adj_loss = F.binary_cross_entropy_with_logits(
            outputs["adjacency_logits"], targets["adjacency"], reduction="none"
        )
        adj_loss = (adj_loss * adj_mask).sum() / adj_mask.sum().clamp(min=1)

        # Weighted total
        total = presence_loss * 1.0 + type_loss * 2.0 + bbox_loss * 5.0 + adj_loss * 1.0

        return {
            "total": total,
            "presence": presence_loss,
            "type": type_loss,
            "bbox": bbox_loss,
            "adjacency": adj_loss,
        }

    def predict(self, pixel_values: torch.Tensor, presence_threshold: float = 0.5) -> list[dict[str, Any]]:
        """
        Inference: return structured room graphs for batch of images.

        Args:
            pixel_values: (B, C, H, W) preprocessed images
            presence_threshold: sigmoid threshold for room presence

        Returns:
            List of dicts with 'rooms' (list of {type, bbox, confidence}) and 'adjacency' (list of pairs)
        """
        self.eval()
        with torch.no_grad():
            outputs = self.forward(pixel_values)

        batch_size = pixel_values.size(0)
        results = []

        for b in range(batch_size):
            presence_probs = torch.sigmoid(outputs["room_presence_logits"][b])  # (max_rooms,)
            room_indices = (presence_probs > presence_threshold).nonzero(as_tuple=True)[0].tolist()

            rooms = []
            for idx in room_indices:
                type_idx = torch.argmax(outputs["room_type_logits"][b, idx]).item()
                bbox = outputs["bbox_logits"][b, idx].tolist()  # [x, y, w, h] normalized
                confidence = presence_probs[idx].item()
                rooms.append({
                    "type": self.ROOM_TYPES[type_idx],
                    "bbox": bbox,
                    "confidence": confidence,
                })

            # Adjacency only among present rooms
            adjacency_pairs = []
            for i in room_indices:
                for j in room_indices:
                    if i < j:  # upper triangle only
                        adj_prob = torch.sigmoid(outputs["adjacency_logits"][b, i, j]).item()
                        if adj_prob > 0.5:
                            adjacency_pairs.append([i, j, adj_prob])

            results.append({
                "rooms": rooms,
                "adjacency": adjacency_pairs,
                "num_rooms": len(rooms),
            })

        return results

    def save_checkpoint(self, path: str, optimizer=None, epoch: int = 0, best_loss: float = float("inf")):
        """Save model checkpoint."""
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        checkpoint = {
            "model_state_dict": self.state_dict(),
            "epoch": epoch,
            "best_loss": best_loss,
        }
        if optimizer:
            checkpoint["optimizer_state_dict"] = optimizer.state_dict()
        torch.save(checkpoint, path)

    def load_checkpoint(self, path: str, optimizer=None, device: str = "cpu") -> tuple[int, float]:
        """Load model checkpoint. Returns (epoch, best_loss)."""
        checkpoint = torch.load(path, map_location=device)
        self.load_state_dict(checkpoint["model_state_dict"])
        if optimizer and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        return checkpoint.get("epoch", 0), checkpoint.get("best_loss", float("inf"))
