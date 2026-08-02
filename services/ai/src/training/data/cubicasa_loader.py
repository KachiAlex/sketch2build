"""CubiCasa5K dataset loader for training.

CubiCasa5K contains 5,000 floor plan images with annotated rooms,
walls, and doors. It's smaller but higher quality than RPlan.

Download from: https://github.com/CubiCasa/CubiCasa5K
"""

import json
import structlog
from pathlib import Path
from typing import Any, Iterator
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image, ImageDraw

from src.training.data.sketch_warp import SketchWarper

logger = structlog.get_logger()


class CubiCasa5KLoader:
    """Loads and processes CubiCasa5K floor plan dataset."""

    ROOM_TYPE_MAP = {
        "Living Room": "living",
        "Kitchen": "kitchen",
        "Bedroom": "bedroom",
        "Bathroom": "bathroom",
        "Dining Room": "dining",
        "Corridor": "hallway",
        "Hallway": "hallway",
        "Entrance": "entrance",
        "Storage": "storage",
        "Balcony": "balcony",
        "Garage": "garage",
        "Office": "office",
        "Utility": "utility",
        "Wardrobe": "storage",
        "Closet": "storage",
        "Toilet": "bathroom",
        "Washroom": "bathroom",
        "Laundry": "utility",
    }

    MIN_ROOM_SIZES = {
        "living": 4.0, "kitchen": 2.5, "bedroom": 3.0, "bathroom": 1.5,
        "dining": 3.0, "hallway": 1.2, "entrance": 1.5, "storage": 1.5,
    }

    def __init__(self, data_dir: str, pixel_size: float = 0.05):
        """
        Args:
            data_dir: Path to CubiCasa5K dataset (contains 'color' and 'label' subdirectories)
            pixel_size: Meters per pixel
        """
        self.data_dir = Path(data_dir)
        self.pixel_size = pixel_size
        self.warper = SketchWarper()

        # Find all image files
        color_dir = self.data_dir / "color"
        if color_dir.exists():
            self.image_files = sorted(color_dir.glob("*.jpg")) + sorted(color_dir.glob("*.png"))
        else:
            self.image_files = sorted(self.data_dir.glob("*.jpg")) + sorted(self.data_dir.glob("*.png"))

        logger.info("CubiCasa5K loader initialized", num_images=len(self.image_files))

    def _parse_cubicasa_annotation(self, image_path: Path) -> dict[str, Any] | None:
        """Parse CubiCasa5K annotation from SVG or JSON."""
        # Try SVG first
        svg_path = image_path.parent.parent / "SVG" / f"{image_path.stem}.svg"
        if not svg_path.exists():
            svg_path = image_path.parent.parent / "svg" / f"{image_path.stem}.svg"

        if svg_path.exists():
            return self._parse_svg_annotation(svg_path)

        # Try JSON
        json_path = image_path.parent.parent / "json" / f"{image_path.stem}.json"
        if json_path.exists():
            return self._parse_json_annotation(json_path)

        logger.warning("No annotation found", image=str(image_path))
        return None

    def _parse_svg_annotation(self, svg_path: Path) -> dict[str, Any] | None:
        """Parse SVG floor plan annotation."""
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
        except ET.ParseError as e:
            logger.warning("SVG parse error", path=str(svg_path), error=str(e))
            return None

        # SVG namespace
        ns = {"svg": "http://www.w3.org/2000/svg"}

        rooms = []
        adjacency = []
        width = 0.0
        depth = 0.0

        # Extract viewBox for dimensions
        viewbox = root.get("viewBox", "0 0 1000 1000")
        try:
            parts = viewbox.split()
            if len(parts) == 4:
                width = float(parts[2]) * self.pixel_size
                depth = float(parts[3]) * self.pixel_size
        except (ValueError, IndexError):
            pass

        # Parse room polygons
        room_elements = root.findall(".//svg:g[@class='room']", ns)
        if not room_elements:
            room_elements = root.findall(".//g[@class='room']")

        for i, room_elem in enumerate(room_elements):
            room_type = room_elem.get("data-type", "utility")
            mapped_type = self.ROOM_TYPE_MAP.get(room_type, "utility")

            # Extract polygon points
            polygon = room_elem.find(".//svg:polygon", ns) or room_elem.find(".//polygon")
            if polygon is not None:
                points_str = polygon.get("points", "")
                try:
                    coords = [float(x) for x in points_str.replace(",", " ").split()]
                    xs = coords[0::2]
                    ys = coords[1::2]
                    x = min(xs) * self.pixel_size
                    y = min(ys) * self.pixel_size
                    w = (max(xs) - min(xs)) * self.pixel_size
                    d = (max(ys) - min(ys)) * self.pixel_size
                except (ValueError, IndexError):
                    continue
            else:
                # Fallback: bounding box from room element
                x, y, w, d = 0, 0, 3, 3

            rooms.append({
                "type": mapped_type,
                "x": x,
                "y": y,
                "w": w,
                "d": d,
            })

        # Parse adjacency from shared edges (doors)
        door_elements = root.findall(".//svg:g[@class='door']", ns) or root.findall(".//g[@class='door']")
        for door in door_elements:
            # Try to find which rooms the door connects
            # This is a heuristic - real implementation needs spatial intersection
            pass

        # Validate
        valid = True
        for room in rooms:
            min_size = self.MIN_ROOM_SIZES.get(room["type"], 1.0)
            if room["w"] < min_size or room["d"] < min_size:
                valid = False
                break

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

    def _parse_json_annotation(self, json_path: Path) -> dict[str, Any] | None:
        """Parse JSON floor plan annotation."""
        try:
            with open(json_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning("JSON parse error", path=str(json_path), error=str(e))
            return None

        rooms = []
        adjacency = []
        width = data.get("width", 1000) * self.pixel_size
        depth = data.get("height", 1000) * self.pixel_size

        for room in data.get("rooms", []):
            room_type = room.get("type", "utility")
            mapped_type = self.ROOM_TYPE_MAP.get(room_type, "utility")

            bbox = room.get("bbox", [0, 0, 100, 100])
            rooms.append({
                "type": mapped_type,
                "x": bbox[0] * self.pixel_size,
                "y": bbox[1] * self.pixel_size,
                "w": (bbox[2] - bbox[0]) * self.pixel_size,
                "d": (bbox[3] - bbox[1]) * self.pixel_size,
            })

        for connection in data.get("connections", []):
            room_a = connection.get("room_a", 0)
            room_b = connection.get("room_b", 0)
            if room_a < len(rooms) and room_b < len(rooms):
                adjacency.append((room_a, room_b))

        valid = True
        for room in rooms:
            min_size = self.MIN_ROOM_SIZES.get(room["type"], 1.0)
            if room["w"] < min_size or room["d"] < min_size:
                valid = False
                break

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
            img = img.resize((256, 256))
            return self.warper.warp(img, size=256)
        except Exception as e:
            logger.warning("Failed to generate sketch", path=str(image_path), error=str(e))
            return None

    def load_sample(self, index: int) -> dict[str, Any] | None:
        """Load a single sample by index."""
        if index >= len(self.image_files):
            return None

        image_path = self.image_files[index]
        annotation = self._parse_cubicasa_annotation(image_path)
        if annotation is None:
            return None

        sketch = self.generate_synthetic_sketch(image_path)
        if sketch is None:
            return None

        clean_plan = self._render_floor_plan(annotation)

        return {
            "id": f"cubicasa_{index}",
            "image": clean_plan,
            "sketch": sketch,
            "rooms": annotation["rooms"],
            "adjacency": annotation["adjacency"],
            "valid": annotation["valid"],
            "width": annotation["width"],
            "depth": annotation["depth"],
            "source": "cubicasa",
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
        """Convert CubiCasa5K dataset to our standard format and save."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "images").mkdir(exist_ok=True)
        (out / "sketches").mkdir(exist_ok=True)

        metadata = []
        for i, sample in enumerate(self.iterate_samples(max_samples)):
            img_path = out / "images" / f"cubicasa_{i:06d}.png"
            sketch_path = out / "sketches" / f"cubicasa_sketch_{i:06d}.png"

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
                "source": "cubicasa",
            })

            if (i + 1) % 500 == 0:
                logger.info("CubiCasa5K conversion progress", processed=i + 1)

        with open(out / "metadata.json", "w") as f:
            json.dump(metadata, f)

        logger.info("CubiCasa5K dataset saved", output_dir=str(out), num_samples=len(metadata))
        return out
