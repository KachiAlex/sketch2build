"""Procedural synthetic floor plan generator.

Generates millions of valid/invalid floor plan + room graph pairs
for training the layout diffusion model and vision encoder.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Iterator
from PIL import Image, ImageDraw
import numpy as np


@dataclass
class Room:
    type: str
    x: float
    y: float
    width: float
    depth: float


@dataclass
class FloorPlan:
    rooms: list[Room] = field(default_factory=list)
    adjacency: list[tuple[int, int]] = field(default_factory=list)
    walls: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    doors: list[tuple[tuple[float, float], tuple[float, float]]] = field(default_factory=list)
    width: float = 0.0
    depth: float = 0.0

    def to_image(self, size: int = 256, line_width: int = 2) -> Image.Image:
        """Render floor plan as a black-and-white line drawing."""
        img = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(img)

        scale = size / max(self.width, self.depth, 1.0)
        offset_x = (size - self.width * scale) / 2
        offset_y = (size - self.depth * scale) / 2

        def to_px(x, y):
            return (offset_x + x * scale, offset_y + y * scale)

        # Draw walls
        for (x1, y1), (x2, y2) in self.walls:
            draw.line([to_px(x1, y1), to_px(x2, y2)], fill="black", width=line_width)

        # Draw doors
        for (x1, y1), (x2, y2) in self.doors:
            draw.line([to_px(x1, y1), to_px(x2, y2)], fill="white", width=line_width + 1)

        # Draw room labels (small text, for debug)
        for room in self.rooms:
            cx, cy = to_px(room.x + room.width / 2, room.y + room.depth / 2)
            draw.text((cx - 10, cy - 5), room.type[:3], fill="gray")

        return img

    def to_sketch(self, size: int = 256, distortion: float = 0.05) -> Image.Image:
        """Generate a sketch-like version with wobbly lines and noise."""
        plan_img = self.to_image(size)
        arr = np.array(plan_img).astype(np.float32)

        # Add slight perlin-like noise distortion to wall lines
        noise = np.random.normal(0, distortion * 255, arr.shape).astype(np.float32)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

        # Add random dropout (gaps in lines) to simulate hand-drawn imperfect lines
        mask = np.random.random(arr.shape[:2]) > 0.02
        arr[~mask] = 255

        return Image.fromarray(arr)


class ProceduralLayoutGenerator:
    """Generates synthetic floor plans procedurally."""

    ROOM_TYPES = ["living", "kitchen", "bedroom", "bathroom", "dining", "hallway", "entrance", "storage"]
    MIN_ROOM_SIZE = 2.5
    MAX_ROOM_SIZE = 8.0

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def generate(
        self,
        num_rooms: int | None = None,
        plot_width: float | None = None,
        plot_depth: float | None = None,
        valid: bool = True,
    ) -> FloorPlan:
        """Generate a single floor plan."""
        if num_rooms is None:
            num_rooms = random.randint(3, 8)
        if plot_width is None:
            plot_width = random.uniform(10, 25)
        if plot_depth is None:
            plot_depth = random.uniform(10, 25)

        rooms = []
        adjacency = []
        walls = []
        doors = []

        # Simple grid-based placement (TODO: replace with graph-based growth)
        x, y = 0, 0
        row_height = 0

        for i in range(num_rooms):
            room_type = random.choice(self.ROOM_TYPES)
            width = random.uniform(self.MIN_ROOM_SIZE, min(self.MAX_ROOM_SIZE, plot_width - x))
            depth = random.uniform(self.MIN_ROOM_SIZE, min(self.MAX_ROOM_SIZE, plot_depth / 2))

            if x + width > plot_width:
                x = 0
                y += row_height + 0.2
                row_height = 0

            if y + depth > plot_depth:
                break

            room = Room(type=room_type, x=x, y=y, width=width, depth=depth)
            rooms.append(room)

            # Walls
            walls.extend([
                ((x, y), (x + width, y)),
                ((x + width, y), (x + width, y + depth)),
                ((x + width, y + depth), (x, y + depth)),
                ((x, y + depth), (x, y)),
            ])

            # Adjacency to previous room
            if i > 0 and x > 0:
                adjacency.append((i - 1, i))
                # Door between rooms
                door_y = y + depth / 2
                doors.append(((x - 0.2, door_y - 0.4), (x + 0.2, door_y + 0.4)))

            x += width + 0.2
            row_height = max(row_height, depth)

        plan = FloorPlan(
            rooms=rooms,
            adjacency=adjacency,
            walls=walls,
            doors=doors,
            width=plot_width,
            depth=plot_depth,
        )

        if not valid:
            # Introduce violations for contrastive learning
            plan = self._add_violations(plan)

        return plan

    def _add_violations(self, plan: FloorPlan) -> FloorPlan:
        """Introduce building code violations into a plan."""
        violation_type = random.choice(["overlap", "tiny_room", "no_entrance", "no_bathroom"])

        if violation_type == "overlap" and len(plan.rooms) > 1:
            # Make two rooms overlap
            r1 = plan.rooms[0]
            r2 = plan.rooms[1]
            r2.x = r1.x + r1.width / 2
            r2.y = r1.y + r1.depth / 2

        elif violation_type == "tiny_room":
            # Make one room too small
            if plan.rooms:
                plan.rooms[0].width = 0.5
                plan.rooms[0].depth = 0.5

        elif violation_type == "no_entrance":
            # Remove entrance if present
            plan.rooms = [r for r in plan.rooms if r.type != "entrance"]

        elif violation_type == "no_bathroom":
            # Remove bathroom if present
            plan.rooms = [r for r in plan.rooms if r.type != "bathroom"]

        return plan

    def generate_batch(
        self,
        batch_size: int,
        valid_ratio: float = 0.7,
    ) -> Iterator[FloorPlan]:
        """Generate a batch of floor plans with a mix of valid/invalid."""
        for _ in range(batch_size):
            is_valid = random.random() < valid_ratio
            yield self.generate(valid=is_valid)


class SyntheticDatasetBuilder:
    """Builds a large synthetic dataset and saves it to disk."""

    def __init__(self, output_dir: str, image_size: int = 256):
        self.output_dir = output_dir
        self.image_size = image_size
        self.generator = ProceduralLayoutGenerator()

    def build(self, num_samples: int = 100_000, valid_ratio: float = 0.7) -> None:
        """Generate and save N samples."""
        import json
        from pathlib import Path

        out = Path(self.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "images").mkdir(exist_ok=True)
        (out / "sketches").mkdir(exist_ok=True)

        metadata = []
        for i in range(num_samples):
            plan = self.generator.generate(valid=random.random() < valid_ratio)

            plan_img = plan.to_image(self.image_size)
            sketch_img = plan.to_sketch(self.image_size)

            img_path = out / "images" / f"plan_{i:06d}.png"
            sketch_path = out / "sketches" / f"sketch_{i:06d}.png"
            plan_img.save(img_path)
            sketch_img.save(sketch_path)

            metadata.append({
                "id": i,
                "image": str(img_path.relative_to(out)),
                "sketch": str(sketch_path.relative_to(out)),
                "rooms": [{"type": r.type, "x": r.x, "y": r.y, "w": r.width, "d": r.depth} for r in plan.rooms],
                "adjacency": plan.adjacency,
                "valid": not self._has_violations(plan),
                "width": plan.width,
                "depth": plan.depth,
            })

            if (i + 1) % 1000 == 0:
                print(f"Generated {i + 1}/{num_samples} samples")

        with open(out / "metadata.json", "w") as f:
            json.dump(metadata, f)

        print(f"Dataset saved to {out}")

    def _has_violations(self, plan: FloorPlan) -> bool:
        # Simple heuristic: check for tiny rooms
        for r in plan.rooms:
            if r.width < 1.5 or r.depth < 1.5:
                return True
        # Check for bathroom presence
        has_bath = any(r.type == "bathroom" for r in plan.rooms)
        if not has_bath and len(plan.rooms) > 3:
            return True
        return False
