"""Sketch understanding inference module."""

import base64
import io
import os
from typing import Any

import structlog
import torch
from PIL import Image
from transformers import CLIPProcessor

from src.config import get_settings
from src.models.vision.sketch_encoder import SketchEncoderModel

logger = structlog.get_logger()
settings = get_settings()


class SketchEncoder:
    """Encodes architectural sketches into structured room graphs.

    Loads a fine-tuned SketchEncoderModel checkpoint if available,
    otherwise falls back to base CLIP with placeholder detection.
    """

    def __init__(self, model_name: str | None = None, checkpoint_path: str | None = None):
        self.model_name = model_name or settings.vision_model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = CLIPProcessor.from_pretrained(self.model_name)

        # Try loading fine-tuned checkpoint
        ckpt_path = checkpoint_path or os.path.join(
            str(settings.models_dir), "vision_encoder", "best.pt"
        )

        if os.path.exists(ckpt_path):
            try:
                self.model = SketchEncoderModel(pretrained_model=self.model_name)
                self.model.load_checkpoint(ckpt_path, device=self.device)
                self.model.to(self.device)
                self.model.eval()
                self._fine_tuned = True
                logger.info("SketchEncoder loaded fine-tuned checkpoint", path=ckpt_path, device=self.device)
            except Exception as e:
                logger.warning("Failed to load checkpoint, using base CLIP", error=str(e))
                self.model = None
                self._fine_tuned = False
        else:
            self.model = None
            self._fine_tuned = False
            logger.info("SketchEncoder using placeholder (no checkpoint found)", path=ckpt_path)

    def encode(self, base64_image: str) -> dict[str, Any]:
        """Decode base64 sketch image and extract structured room graph."""
        image = self._decode_image(base64_image)

        if self._fine_tuned and self.model is not None:
            return self._encode_with_model(image)
        else:
            return self._encode_placeholder(image)

    def _encode_with_model(self, image: Image.Image) -> dict[str, Any]:
        """Use fine-tuned model for room graph extraction."""
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        results = self.model.predict(inputs["pixel_values"])
        result = results[0] if results else {"rooms": [], "adjacency": [], "num_rooms": 0}

        # Convert to pipeline format
        room_types = [r["type"] for r in result["rooms"]]
        bboxes = [r["bbox"] for r in result["rooms"]]
        adjacency = [(a[0], a[1]) for a in result["adjacency"]]

        return {
            "room_types": room_types,
            "bboxes": bboxes,
            "adjacency": adjacency,
            "rooms": result["rooms"],
            "num_rooms": result["num_rooms"],
            "source": "fine_tuned_model",
        }

    def _encode_placeholder(self, image: Image.Image) -> dict[str, Any]:
        """Placeholder: return default room graph when no checkpoint is available."""
        w, h = image.size
        return {
            "room_types": ["living", "kitchen", "bedroom", "bathroom"],
            "bboxes": [
                [0.0, 0.0, 0.5, 0.5],
                [0.5, 0.0, 0.5, 0.3],
                [0.0, 0.5, 0.4, 0.5],
                [0.4, 0.5, 0.3, 0.5],
            ],
            "adjacency": [(0, 1), (0, 2), (1, 3), (2, 3)],
            "rooms": [
                {"type": "living", "bbox": [0.0, 0.0, 0.5, 0.5], "confidence": 0.5},
                {"type": "kitchen", "bbox": [0.5, 0.0, 0.5, 0.3], "confidence": 0.5},
                {"type": "bedroom", "bbox": [0.0, 0.5, 0.4, 0.5], "confidence": 0.5},
                {"type": "bathroom", "bbox": [0.4, 0.5, 0.3, 0.5], "confidence": 0.5},
            ],
            "num_rooms": 4,
            "source": "placeholder",
        }

    def _decode_image(self, base64_image: str) -> Image.Image:
        """Decode base64 string to PIL Image."""
        header, _, data = base64_image.partition(",")
        if not data:
            data = base64_image
        image_bytes = base64.b64decode(data)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
