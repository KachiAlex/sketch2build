"""Sketch understanding inference module."""

import base64
import io
from typing import Any

import structlog
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class SketchEncoder:
    """Encodes architectural sketches into structured room graphs."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.vision_model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # TODO: load fine-tuned checkpoint instead of base CLIP
        self.model = CLIPModel.from_pretrained(self.model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(self.model_name)
        self.model.eval()

        logger.info("SketchEncoder loaded", model=self.model_name, device=self.device)

    def encode(self, base64_image: str) -> dict[str, Any]:
        """Decode base64 sketch image and extract structured room graph."""
        image = self._decode_image(base64_image)

        # TODO: replace with fine-tuned detection head
        # For now, return a placeholder graph
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)

        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)

        logger.info("Sketch encoded", features_shape=image_features.shape)

        return {
            "room_types": ["living", "kitchen", "bedroom", "bath"],  # placeholder
            "adjacency": [],
            "dimensions": {},
            "embedding": image_features.cpu().numpy().tolist(),
        }

    def _decode_image(self, base64_image: str) -> Image.Image:
        """Decode base64 string to PIL Image."""
        header, _, data = base64_image.partition(",")
        if not data:
            data = base64_image
        image_bytes = base64.b64decode(data)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
