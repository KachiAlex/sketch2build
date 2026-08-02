"""Layout generation inference module."""

import os
import structlog
import torch
import numpy as np
from typing import Any

from src.config import get_settings
from src.models.layout.diffusion import LayoutDiffusionModel

logger = structlog.get_logger()
settings = get_settings()


class LayoutGenerator:
    """Generates 2D floor plans from room graphs and style prompts.

    Loads a fine-tuned LayoutDiffusionModel checkpoint if available,
    otherwise falls back to procedural layout generation.
    """

    def __init__(self, model_name: str | None = None, checkpoint_path: str | None = None):
        self.model_name = model_name or settings.layout_diffusion_model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Try loading fine-tuned checkpoint
        ckpt_path = checkpoint_path or os.path.join(
            str(settings.models_dir), "layout_diffusion", "best.pt"
        )

        if os.path.exists(ckpt_path):
            try:
                self.model = LayoutDiffusionModel()
                self.model.load_checkpoint(ckpt_path, device=self.device)
                self.model.to(self.device)
                self.model.eval()
                self._fine_tuned = True
                logger.info("LayoutGenerator loaded fine-tuned checkpoint", path=ckpt_path, device=self.device)
            except Exception as e:
                logger.warning("Failed to load layout checkpoint, using procedural", error=str(e))
                self.model = None
                self._fine_tuned = False
        else:
            self.model = None
            self._fine_tuned = False
            logger.info("LayoutGenerator using procedural (no checkpoint found)", path=ckpt_path)

    def generate(
        self,
        room_graph: dict,
        style: str,
        constraints: dict | None,
        seed: int = 0,
    ) -> dict:
        """Generate a floor plan from a room graph."""
        logger.info(
            "Generating layout",
            rooms=room_graph.get("room_types", []),
            style=style,
            seed=seed,
        )

        if self._fine_tuned and self.model is not None:
            return self._generate_with_model(room_graph, style, constraints, seed)
        else:
            return self._generate_procedural(room_graph, style, constraints, seed)

    def _generate_with_model(
        self,
        room_graph: dict,
        style: str,
        constraints: dict | None,
        seed: int,
    ) -> dict:
        """Use fine-tuned diffusion model for layout generation."""
        torch.manual_seed(seed)

        room_types = room_graph.get("room_types", [])
        bboxes = room_graph.get("bboxes", [])
        adjacency = room_graph.get("adjacency", [])
        max_rooms = 20

        # Pad to max_rooms
        type_indices = [self._room_type_to_idx(r) for r in room_types]
        while len(type_indices) < max_rooms:
            type_indices.append(0)
        while len(bboxes) < max_rooms:
            bboxes.append([0, 0, 0, 0])

        # Build adjacency matrix
        adj_matrix = np.zeros((max_rooms, max_rooms), dtype=np.float32)
        for a, b in adjacency:
            if isinstance(a, int) and isinstance(b, int) and a < max_rooms and b < max_rooms:
                adj_matrix[a][b] = 1
                adj_matrix[b][a] = 1

        # Build mask
        mask = np.zeros(max_rooms, dtype=np.float32)
        mask[:len(room_types)] = 1

        # Convert to tensors
        room_types_t = torch.tensor(type_indices[:max_rooms], dtype=torch.long).unsqueeze(0).to(self.device)
        bboxes_t = torch.tensor(bboxes[:max_rooms], dtype=torch.float32).unsqueeze(0).to(self.device)
        adjacency_t = torch.tensor(adj_matrix, dtype=torch.float32).unsqueeze(0).to(self.device)
        mask_t = torch.tensor(mask, dtype=torch.bool).unsqueeze(0).to(self.device)

        # Generate
        with torch.no_grad():
            generated = self.model.generate(
                room_types=room_types_t,
                bboxes=bboxes_t,
                adjacency=adjacency_t,
                mask=mask_t,
                shape=(1, 3, 256, 256),
                num_inference_steps=50,
            )

        # Convert generated image to room layout
        image = generated[0].cpu().numpy().transpose(1, 2, 0)
        image = ((image + 1) / 2 * 255).clip(0, 255).astype(np.uint8)

        # Extract rooms from generated image (simplified — would use segmentation in production)
        rooms = self._image_to_rooms(image, room_types, bboxes, constraints)

        return {
            "rooms": rooms,
            "adjacency": adjacency,
            "image": image.tolist() if False else None,  # Don't serialize full image
            "style": style,
            "source": "diffusion_model",
            "area_m2": sum(r.get("area", 0) for r in rooms),
        }

    def _generate_procedural(
        self,
        room_graph: dict,
        style: str,
        constraints: dict | None,
        seed: int,
    ) -> dict:
        """Procedural layout generation when no model checkpoint is available."""
        np.random.seed(seed)

        room_types = room_graph.get("room_types", [])
        adjacency = room_graph.get("adjacency", [])
        bboxes = room_graph.get("bboxes", [])

        # Get plot dimensions
        plot_width = 15.0
        plot_depth = 12.0
        if constraints:
            plot_width = constraints.get("plot_width", plot_width)
            plot_depth = constraints.get("plot_depth", plot_depth)

        # Use bboxes from vision encoder if available, otherwise pack rooms
        if bboxes and len(bboxes) == len(room_types):
            rooms = []
            for i, (room_type, bbox) in enumerate(zip(room_types, bboxes)):
                x = bbox[0] * plot_width
                y = bbox[1] * plot_depth
                w = bbox[2] * plot_width
                d = bbox[3] * plot_depth
                rooms.append({
                    "id": f"room_{i}",
                    "type": room_type,
                    "label": f"{room_type}_{i}",
                    "x": round(x, 2),
                    "y": round(y, 2),
                    "w": round(w, 2),
                    "d": round(d, 2),
                    "width": round(w, 2),
                    "depth": round(d, 2),
                    "area": round(w * d, 2),
                    "height": self._get_room_height(room_type),
                    "boundary": [
                        [round(x, 2), round(y, 2)],
                        [round(x + w, 2), round(y, 2)],
                        [round(x + w, 2), round(y + d, 2)],
                        [round(x, 2), round(y + d, 2)],
                    ],
                })
        else:
            # Grid-packing algorithm
            rooms = self._pack_rooms(room_types, plot_width, plot_depth, seed)

        return {
            "rooms": rooms,
            "adjacency": adjacency,
            "plot_width": plot_width,
            "plot_depth": plot_depth,
            "style": style,
            "source": "procedural",
            "area_m2": sum(r["area"] for r in rooms),
        }

    def _pack_rooms(
        self,
        room_types: list[str],
        plot_width: float,
        plot_depth: float,
        seed: int,
    ) -> list[dict]:
        """Pack rooms into a rectangular plot using a simple shelf-packing algorithm."""
        # Sort rooms by typical size (largest first)
        size_order = {"living": 0, "kitchen": 1, "dining": 2, "bedroom": 3, "garage": 4, "office": 5, "bathroom": 6, "utility": 7, "storage": 8, "hallway": 9, "entrance": 10, "balcony": 11}
        sorted_rooms = sorted(enumerate(room_types), key=lambda x: size_order.get(x[1], 5))

        # Target areas
        target_areas = {
            "living": 20, "kitchen": 10, "bedroom": 12, "bathroom": 5,
            "dining": 12, "hallway": 4, "entrance": 3, "balcony": 5,
            "storage": 3, "garage": 20, "office": 10, "utility": 5,
        }

        rooms = []
        x, y = 0.0, 0.0
        row_height = 0.0
        margin = 0.2

        for orig_idx, room_type in sorted_rooms:
            area = target_areas.get(room_type, 10.0)
            # Try to fit in remaining row width
            remaining_w = plot_width - x - margin
            if remaining_w < 3.0:  # Start new row
                x = 0.0
                y += row_height + margin
                row_height = 0.0
                remaining_w = plot_width - margin

            # Determine width and depth
            w = min(max(area ** 0.5 * 1.3, 3.0), remaining_w)
            d = max(area / w, 2.5)

            # Clamp to plot
            if y + d > plot_depth:
                d = plot_depth - y - margin
                w = max(area / d, 3.0)

            rooms.append({
                "id": f"room_{orig_idx}",
                "type": room_type,
                "label": f"{room_type}_{orig_idx}",
                "x": round(x, 2),
                "y": round(y, 2),
                "w": round(w, 2),
                "d": round(d, 2),
                "width": round(w, 2),
                "depth": round(d, 2),
                "area": round(w * d, 2),
                "height": self._get_room_height(room_type),
                "boundary": [
                    [round(x, 2), round(y, 2)],
                    [round(x + w, 2), round(y, 2)],
                    [round(x + w, 2), round(y + d, 2)],
                    [round(x, 2), round(y + d, 2)],
                ],
            })

            x += w + margin
            row_height = max(row_height, d)

        # Sort rooms back to original order
        rooms.sort(key=lambda r: int(r["id"].split("_")[1]))
        return rooms

    def _room_type_to_idx(self, room_type: str) -> int:
        """Convert room type string to index."""
        room_types = [
            "living", "kitchen", "bedroom", "bathroom", "dining",
            "hallway", "entrance", "balcony", "storage", "garage",
            "office", "utility",
        ]
        return room_types.index(room_type) if room_type in room_types else 0

    def _get_room_height(self, room_type: str) -> float:
        """Get default ceiling height for room type."""
        heights = {
            "living": 2.7, "kitchen": 2.7, "bedroom": 2.7, "bathroom": 2.4,
            "dining": 2.7, "hallway": 2.4, "entrance": 2.4, "balcony": 2.4,
            "storage": 2.4, "garage": 2.5, "office": 2.7, "utility": 2.4,
        }
        return heights.get(room_type, 2.7)

    def _image_to_rooms(
        self,
        image: np.ndarray,
        room_types: list[str],
        bboxes: list,
        constraints: dict | None,
    ) -> list[dict]:
        """Convert generated image to room layout (simplified)."""
        # In production, this would use segmentation to extract room boundaries
        # For now, use the input bboxes mapped to plot dimensions
        plot_width = constraints.get("plot_width", 15.0) if constraints else 15.0
        plot_depth = constraints.get("plot_depth", 12.0) if constraints else 12.0

        rooms = []
        for i, room_type in enumerate(room_types):
            if i < len(bboxes):
                bbox = bboxes[i]
                x = bbox[0] * plot_width
                y = bbox[1] * plot_depth
                w = bbox[2] * plot_width
                d = bbox[3] * plot_depth
            else:
                x, y, w, d = 0, 0, 4, 4

            rooms.append({
                "id": f"room_{i}",
                "type": room_type,
                "label": f"{room_type}_{i}",
                "x": round(x, 2),
                "y": round(y, 2),
                "w": round(w, 2),
                "d": round(d, 2),
                "width": round(w, 2),
                "depth": round(d, 2),
                "area": round(w * d, 2),
                "height": self._get_room_height(room_type),
                "boundary": [
                    [round(x, 2), round(y, 2)],
                    [round(x + w, 2), round(y, 2)],
                    [round(x + w, 2), round(y + d, 2)],
                    [round(x, 2), round(y + d, 2)],
                ],
            })

        return rooms
