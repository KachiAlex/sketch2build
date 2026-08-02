"""RPlan dataset loader for training.

RPlan dataset contains 80,000+ floor plans from real residential buildings.
Each plan has annotated rooms, walls, and doors.

Download from: https://github.com/SeanCodingChang/RPLAN
"""

import json
import structlog
from pathlib import Path
from typing import Any, Iterator
import numpy as np
from PIL import Image, ImageDraw
import cv2

from src.training.data.sketch_warp import SketchWarper

logger = structlog.get_logger()


class RPlanLoader:
    """Loads and processes RPlan dataset floor plans."""

    ROOM_TYPE_MAP = {
        0: "living",
        1: "kitchen",
        2: "bedroom",
        3: "bathroom",
        4: "dining",
        5: "hallway",
        6: "entrance",
        7: "storage",
        8: "balcony",
        9: "garage",
        10: "office",
        11: "utility",
    }

    MIN_ROOM_SIZES = {
        "living": 4.0, "kitchen": 2.5, "bedroom": 3.0, "bathroom": 1.5,
        "dining": 3.0, "hallway": 1.2, "entrance": 1.5, "storage": 1.5,
    }

    def __init__(self, data_dir: str, pixel_size: float = 0.05):
        """
        Args:
            data_dir: Path to RPlan dataset directory (contains .png files and metadata)
            pixel_size: Meters per pixel in the floor plan images
        """
        self.data_dir = Path(data_dir)
        self.pixel_size = pixel_size
        self.warper = SketchWarper()

        # Find all floor plan files
        self.image_files = sorted(self.data_dir.glob("*.png"))
        self.json_files = sorted(self.data_dir.glob("*.json"))
        logger.info("RPlan loader initialized", num_images=len(self.image_files), num_jsons=len(self.json_files))

    def _parse_rplan_annotation(self, json_path: Path) -> dict[str, Any] | None:
        """Parse RPlan JSON annotation into our format."""
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning("Failed to parse RPlan annotation", path=str(json_path), error=str(e))
            return None

        rooms = []
        adjacency = []
        width = data.get("width", 0) * self.pixel_size
        depth = data.get("height", 0) * self.pixel_size

        for room in data.get("rooms", []):
            room_type_idx = room.get("type", 0)
            room_type = self.ROOM_TYPE_MAP.get(room_type_idx, "utility")

            # RPlan annotations are in pixel coordinates
            bbox = room.get("bbox", [0, 0, 0, 0])
            x = bbox[0] * self.pixel_size
            y = bbox[1] * self.pixel_size
            w = (bbox[2] - bbox[0]) * self.pixel_size
            d = (bbox[3] - bbox[1]) * self.pixel_size

            rooms.append({
                "type": room_type,
                "x": x,
                "y": y,
                "w": w,
                "d": d,
            })

        # Parse adjacency from wall connections
        for connection in data.get("connections", []):
            room_a = connection.get("room_a", 0)
            room_b = connection.get("room_b", 0)
            if room_a < len(rooms) and room_b < len(rooms):
                adjacency.append((room_a, room_b))

        # Validate: check for minimum room sizes
        valid = True
        for room in rooms:
            min_size = self.MIN_ROOM_SIZES.get(room["type"], 1.0)
            if room["w"] < min_size or room["d"] < min_size:
                valid = False
                break

        # Check for bathroom
        has_bathroom = any(r["type"] == "bathroom" for r in rooms)
        if not has_bathroom and len(rooms) > 3:
            valid = False

        return {
            "rooms": rooms,
            "adjacency": adjacency,
            "width": width,
            "depth": depth,
            "valid": valid,
        }

    def _render_floor_plan(self, annotation: dict) -> Image.Image:
        """Render annotation as a clean floor plan image."""
        size = 256
        scale = min(size / annotation["width"], size / annotation["depth"]) if annotation["width"] > 0 and annotation["depth"] > 0 else 10

        img = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(img)

        offset_x = (size - annotation["width"] * scale) / 2
        offset_y = (size - annotation["depth"] * scale) / 2

        for room in annotation["rooms"]:
            x1 = offset_x + room["x"] * scale
            y1 = offset_y + room["y"] * scale
            x2 = x1 + room["w"] * scale
            y2 = y1 + room["d"] * scale
            draw.rectangle([x1, y1, x2, y2], outline="black", width=2)

        return img

    def generate_synthetic_sketch(self, image_path: Path) -> Image.Image | None:
        """Generate a sketch-like version from a real floor plan image."""
        try:
            img = Image.open(image_path).convert("RGB")
            # Resize to standard size
            img = img.resize((256, 256))
            # Apply sketch warping
            return self.warper.warp(img, size=256)
        except Exception as e:
            logger.warning("Failed to generate sketch", path=str(image_path), error=str(e))
            return None

    def load_sample(self, index: int) -> dict[str, Any] | None:
        """Load a single sample by index."""
        if index >= len(self.image_files):
            return None

        image_path = self.image_files[index]
        json_path = image_path.with_suffix(".json")

        if not json_path.exists():
            return None

        annotation = self._parse_rplan_annotation(json_path)
        if annotation is None:
            return None

        # Generate synthetic sketch from the image
        sketch = self.generate_synthetic_sketch(image_path)
        if sketch is None:
            return None

        # Render clean floor plan from annotation
        clean_plan = self._render_floor_plan(annotation)

        return {
            "id": f"rplan_{index}",
            "image": clean_plan,
            "sketch": sketch,
            "rooms": annotation["rooms"],
            "adjacency": annotation["adjacency"],
            "valid": annotation["valid"],
            "width": annotation["width"],
            "depth": annotation["depth"],
            "source": "rplan",
        }

    def iterate_samples(self, max_samples: int | None = None) -> Iterator[dict[str, Any]]:
        """Iterate over all samples."""
        count = 0
        for i in range(len(self.image_files)):
            if max_samples and count >= max_samples:
                break
            sample = self.load_sample(i)
            if sample is not None:
                count += 1
                yield sample

    def save_to_disk(self, output_dir: str, max_samples: int | None = None) -> Path:
        """Convert RPlan dataset to our standard format and save."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "images").mkdir(exist_ok=True)
        (out / "sketches").mkdir(exist_ok=True)

        metadata = []
        for i, sample in enumerate(self.iterate_samples(max_samples)):
            img_path = out / "images" / f"rplan_{i:06d}.png"
            sketch_path = out / "sketches" / f"rplan_sketch_{i:06d}.png"

            sample["image"].save(img_path)
            sample["sketch"].save(sketch_path)

            metadata.append({
                "id": sample["id"],
                "image": str(img_path.relative_to(out)),
                "sketch": str(sketch_path.relative_to(out)),
                "rooms": sample["rooms"],
                "adjacency": sample["adjacency"],
                "valid": sample["valid"],
                "width": sample["width"],
                "depth": sample["depth"],
                "source": "rplan",
            })

            if (i + 1) % 1000 == 0:
                logger.info("RPlan conversion progress", processed=i + 1)

        with open(out / "metadata.json", "w") as f:
            json.dump(metadata, f)

        logger.info("RPlan dataset saved", output_dir=str(out), num_samples=len(metadata))
        return out
