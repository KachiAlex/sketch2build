"""Generate synthetic sketches from real floor plans.

Takes real floor plan images (e.g., from RPlan dataset) and applies
edge detection, warping, and noise to create realistic hand-drawn sketches.
"""

import cv2
import numpy as np
from PIL import Image, ImageFilter
import random


class SketchWarper:
    """Transforms clean floor plan images into sketch-like drawings."""

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def warp(self, image: Image.Image, size: int = 256) -> Image.Image:
        """Apply full sketch warping pipeline to a clean floor plan image."""
        img = image.convert("L").resize((size, size))
        arr = np.array(img, dtype=np.float32)

        # Step 1: Edge detection (Canny) to extract wall lines
        edges = cv2.Canny(arr.astype(np.uint8), 50, 150)

        # Step 2: Dilate edges to make lines thicker like hand-drawn
        kernel = np.ones((2, 2), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)

        # Step 3: Apply elastic deformation (wobbly lines)
        edges = self._elastic_deform(edges, alpha=size * 0.8, sigma=size * 0.05)

        # Step 4: Add line dropout (gaps in lines)
        edges = self._line_dropout(edges, dropout_prob=0.08)

        # Step 5: Add Gaussian noise
        noise = np.random.normal(0, 15, edges.shape).astype(np.float32)
        edges = np.clip(edges.astype(np.float32) + noise, 0, 255)

        # Step 6: Add random scribbles / hatching (architectural sketch style)
        edges = self._add_hatching(edges, num_hatches=random.randint(0, 5))

        # Step 7: Invert to black lines on white background
        sketch = 255 - edges.astype(np.uint8)

        # Step 8: Add background noise (paper texture simulation)
        sketch = self._add_paper_texture(sketch)

        return Image.fromarray(sketch).convert("RGB")

    def _elastic_deform(self, image: np.ndarray, alpha: float, sigma: float) -> np.ndarray:
        """Apply elastic deformation to simulate hand-drawn wobble."""
        shape = image.shape
        dx = cv2.GaussianBlur((np.random.rand(*shape) * 2 - 1), (0, 0), sigma) * alpha
        dy = cv2.GaussianBlur((np.random.rand(*shape) * 2 - 1), (0, 0), sigma) * alpha

        x, y = np.meshgrid(np.arange(shape[1]), np.arange(shape[0]))
        map_x = (x + dx).astype(np.float32)
        map_y = (y + dy).astype(np.float32)

        return cv2.remap(image.astype(np.float32), map_x, map_y, interpolation=cv2.INTER_LINEAR)

    def _line_dropout(self, image: np.ndarray, dropout_prob: float = 0.05) -> np.ndarray:
        """Randomly erase small segments of lines to simulate imperfect drawing."""
        mask = np.random.random(image.shape) > dropout_prob
        return image * mask.astype(np.uint8)

    def _add_hatching(self, image: np.ndarray, num_hatches: int = 3) -> np.ndarray:
        """Add diagonal hatching lines to shaded areas (common in architectural sketches)."""
        h, w = image.shape
        result = image.copy().astype(np.float32)

        for _ in range(num_hatches):
            # Random diagonal hatching in a random region
            x1 = random.randint(0, w - 20)
            y1 = random.randint(0, h - 20)
            x2 = x1 + random.randint(10, 30)
            y2 = y1 + random.randint(10, 30)

            # Draw diagonal lines in the region
            for offset in range(0, x2 - x1, 3):
                cv2.line(
                    result,
                    (x1 + offset, y1),
                    (x1 + offset - 5, y2),
                    color=128,  # gray hatching
                    thickness=1,
                )

        return np.clip(result, 0, 255).astype(np.uint8)

    def _add_paper_texture(self, image: np.ndarray) -> np.ndarray:
        """Simulate paper texture with subtle grain."""
        grain = np.random.normal(0, 3, image.shape).astype(np.float32)
        return np.clip(image.astype(np.float32) + grain, 0, 255).astype(np.uint8)

    def batch_warp(self, images: list[Image.Image], size: int = 256) -> list[Image.Image]:
        """Warp a batch of images."""
        return [self.warp(img, size) for img in images]
