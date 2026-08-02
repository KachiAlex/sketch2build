"""Graph-based procedural floor plan generator (House-GAN style).

Generates more realistic floor plans by growing rooms from a seed room
using adjacency constraints and graph-based expansion.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Iterator, Optional
from PIL import Image, ImageDraw
import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union


@dataclass
class Room:
    type: str
    x: float
    y: float
    width: float
    depth: float
    id: int = 0

    @property
    def polygon(self) -> Polygon:
        return box(self.x, self.y, self.x + self.width, self.y + self.depth)

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.depth / 2)

    def overlaps(self, other: "Room", gap: float = 0.0) -> bool:
        return self.polygon.buffer(gap).intersects(other.polygon.buffer(gap))

    def shared_edge(self, other: "Room") -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
        """Returns the shared edge (doorway) between two adjacent rooms, if any."""
        intersection = self.polygon.boundary.intersection(other.polygon.boundary)
        if intersection.is_empty or intersection.length < 0.5:
            return None
        coords = list(intersection.coords)
        if len(coords) >= 2:
            return (coords[0], coords[-1])
        return None


@dataclass
class FloorPlan:
    rooms: list[Room] = field(default_factory=list)
    adjacency: list[tuple[int, int]] = field(default_factory=list)
    plot_width: float = 20.0
    plot_depth: float = 20.0
    entrance_position: tuple[float, float] = (0.0, 0.0)

    def to_image(self, size: int = 256, line_width: int = 2, show_labels: bool = False) -> Image.Image:
        img = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(img)

        scale = size / max(self.plot_width, self.plot_depth, 1.0)
        offset_x = (size - self.plot_width * scale) / 2
        offset_y = (size - self.plot_depth * scale) / 2

        def to_px(x, y):
            return (offset_x + x * scale, offset_y + y * scale)

        # Draw plot boundary
        draw.rectangle(
            [to_px(0, 0), to_px(self.plot_width, self.plot_depth)],
            outline="gray",
            width=1,
        )

        # Draw room walls
        for room in self.rooms:
            draw.rectangle(
                [to_px(room.x, room.y), to_px(room.x + room.width, room.y + room.depth)],
                outline="black",
                width=line_width,
            )
            if show_labels:
                cx, cy = to_px(room.x + room.width / 2, room.y + room.depth / 2)
                draw.text((cx - 15, cy - 5), room.type[:4], fill="black")

        # Draw doors (white gaps in walls)
        for i, j in self.adjacency:
            if i >= len(self.rooms) or j >= len(self.rooms):
                continue
            edge = self.rooms[i].shared_edge(self.rooms[j])
            if edge:
                (x1, y1), (x2, y2) = edge
                draw.line(
                    [to_px(x1, y1), to_px(x2, y2)],
                    fill="white",
                    width=line_width + 2,
                )

        # Draw entrance
        ex, ey = self.entrance_position
        draw.ellipse(
            [to_px(ex - 0.3, ey - 0.3), to_px(ex + 0.3, ey + 0.3)],
            fill="blue",
            outline="blue",
        )

        return img

    def to_sketch(self, size: int = 256, distortion: float = 0.03) -> Image.Image:
        plan_img = self.to_image(size, show_labels=False)
        arr = np.array(plan_img).astype(np.float32)

        # Add noise
        noise = np.random.normal(0, distortion * 255, arr.shape).astype(np.float32)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)

        # Line dropout
        mask = np.random.random(arr.shape[:2]) > 0.015
        arr[~mask] = 255

        return Image.fromarray(arr)

    def total_area(self) -> float:
        """Union area of all rooms (no double counting)."""
        if not self.rooms:
            return 0.0
        union = unary_union([r.polygon for r in self.rooms])
        return union.area

    def building_footprint(self) -> float:
        """Bounding box area of all rooms."""
        if not self.rooms:
            return 0.0
        union = unary_union([r.polygon for r in self.rooms])
        bounds = union.bounds
        return (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])

    def far(self) -> float:
        """Floor Area Ratio."""
        return self.total_area() / (self.plot_width * self.plot_depth) if self.plot_width * self.plot_depth > 0 else 0.0


class GraphBasedLayoutGenerator:
    """Generates floor plans using graph-based room growth."""

    ROOM_TYPES = ["living", "kitchen", "bedroom", "bathroom", "dining", "hallway", "entrance", "storage"]

    # Adjacency preferences: which rooms should be next to each other
    ADJACENCY_PREFERENCES = {
        "entrance": ["hallway", "living"],
        "living": ["kitchen", "dining", "hallway", "bedroom"],
        "kitchen": ["dining", "living", "storage"],
        "dining": ["kitchen", "living"],
        "bedroom": ["bathroom", "hallway", "living"],
        "bathroom": ["bedroom", "hallway"],
        "hallway": ["entrance", "bedroom", "bathroom", "living"],
        "storage": ["kitchen"],
    }

    # Minimum room sizes (meters)
    MIN_SIZES = {
        "living": (4.0, 4.0),
        "kitchen": (2.5, 2.5),
        "bedroom": (3.0, 3.0),
        "bathroom": (1.5, 2.0),
        "dining": (3.0, 3.0),
        "hallway": (1.2, 2.0),
        "entrance": (1.5, 1.5),
        "storage": (1.5, 1.5),
    }

    # Maximum room sizes (meters)
    MAX_SIZES = {
        "living": (8.0, 8.0),
        "kitchen": (5.0, 5.0),
        "bedroom": (5.0, 5.0),
        "bathroom": (3.0, 4.0),
        "dining": (6.0, 6.0),
        "hallway": (2.0, 6.0),
        "entrance": (3.0, 3.0),
        "storage": (3.0, 3.0),
    }

    def __init__(self, seed: int | None = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def _random_size(self, room_type: str) -> tuple[float, float]:
        min_w, min_d = self.MIN_SIZES[room_type]
        max_w, max_d = self.MAX_SIZES[room_type]
        width = random.uniform(min_w, max_w)
        depth = random.uniform(min_d, max_d)
        return width, depth

    def _place_room_adjacent(
        self,
        existing_room: Room,
        room_type: str,
        existing_rooms: list[Room],
        plot_width: float,
        plot_depth: float,
        max_attempts: int = 50,
    ) -> Optional[Room]:
        """Try to place a new room adjacent to an existing room."""
        width, depth = self._random_size(room_type)

        for _ in range(max_attempts):
            # Pick a random side of the existing room
            side = random.choice(["top", "bottom", "left", "right"])

            if side == "top":
                x = existing_room.x + random.uniform(-0.5, existing_room.width - width + 0.5)
                y = existing_room.y + existing_room.depth
            elif side == "bottom":
                x = existing_room.x + random.uniform(-0.5, existing_room.width - width + 0.5)
                y = existing_room.y - depth
            elif side == "left":
                x = existing_room.x - width
                y = existing_room.y + random.uniform(-0.5, existing_room.depth - depth + 0.5)
            else:  # right
                x = existing_room.x + existing_room.width
                y = existing_room.y + random.uniform(-0.5, existing_room.depth - depth + 0.5)

            # Keep within plot bounds with some margin
            x = max(0.0, min(x, plot_width - width))
            y = max(0.0, min(y, plot_depth - depth))

            new_room = Room(type=room_type, x=x, y=y, width=width, depth=depth)

            # Check overlap with existing rooms
            if all(not new_room.overlaps(r, gap=0.1) for r in existing_rooms):
                return new_room

        return None

    def generate(
        self,
        num_rooms: int | None = None,
        plot_width: float | None = None,
        plot_depth: float | None = None,
        required_rooms: list[str] | None = None,
        valid: bool = True,
    ) -> FloorPlan:
        """Generate a floor plan using graph-based growth."""
        if plot_width is None:
            plot_width = random.uniform(12, 25)
        if plot_depth is None:
            plot_depth = random.uniform(12, 25)

        if required_rooms is None:
            required_rooms = ["entrance", "living", "kitchen", "bedroom", "bathroom"]
            if num_rooms and num_rooms > len(required_rooms):
                extra = random.sample(["dining", "hallway", "storage", "bedroom"], num_rooms - len(required_rooms))
                required_rooms.extend(extra)

        rooms: list[Room] = []
        adjacency: list[tuple[int, int]] = []
        entrance_position = (0.0, 0.0)

        # Place entrance first (near edge of plot)
        entrance_width, entrance_depth = self._random_size("entrance")
        entrance_x = random.uniform(0, plot_width - entrance_width)
        entrance_y = 0.0 if random.random() > 0.5 else plot_depth - entrance_depth
        entrance = Room(type="entrance", x=entrance_x, y=entrance_y, width=entrance_width, depth=entrance_depth, id=0)
        rooms.append(entrance)
        entrance_position = (entrance_x + entrance_width / 2, entrance_y + entrance_depth / 2)

        # Grow from entrance
        queue = [entrance]
        placed_types = {"entrance"}
        room_idx = 1

        while queue and len(rooms) < len(required_rooms):
            current = queue.pop(0)
            current_type = current.type

            # Find preferred adjacent room types
            preferences = self.ADJACENCY_PREFERENCES.get(current_type, [])
            needed = [r for r in required_rooms if r not in placed_types]

            # Prefer needed rooms that also prefer being next to current
            candidates = [r for r in needed if r in preferences]
            if not candidates:
                candidates = needed
            if not candidates:
                break

            next_type = random.choice(candidates[:3])  # Pick from top preferences

            new_room = self._place_room_adjacent(current, next_type, rooms, plot_width, plot_depth)
            if new_room:
                new_room.id = room_idx
                rooms.append(new_room)
                adjacency.append((current.id, room_idx))
                placed_types.add(next_type)
                queue.append(new_room)
                room_idx += 1
            else:
                # Try another room type
                if candidates and len(candidates) > 1:
                    queue.append(current)  # Retry later

        # If we haven't placed all required rooms, add them randomly
        for room_type in required_rooms:
            if room_type not in placed_types:
                width, depth = self._random_size(room_type)
                for _ in range(100):
                    x = random.uniform(0, max(0, plot_width - width))
                    y = random.uniform(0, max(0, plot_depth - depth))
                    new_room = Room(type=room_type, x=x, y=y, width=width, depth=depth, id=room_idx)
                    if all(not new_room.overlaps(r, gap=0.1) for r in rooms):
                        rooms.append(new_room)
                        placed_types.add(room_type)
                        room_idx += 1
                        break

        plan = FloorPlan(
            rooms=rooms,
            adjacency=adjacency,
            plot_width=plot_width,
            plot_depth=plot_depth,
            entrance_position=entrance_position,
        )

        if not valid:
            plan = self._add_violations(plan)

        return plan

    def _add_violations(self, plan: FloorPlan) -> FloorPlan:
        """Introduce building code violations for contrastive learning."""
        violation_type = random.choice(["overlap", "tiny_room", "no_bathroom", "no_entrance"])

        if violation_type == "overlap" and len(plan.rooms) > 1:
            r1 = random.choice(plan.rooms)
            candidates = [r for r in plan.rooms if r.id != r1.id]
            if candidates:
                r2 = random.choice(candidates)
                r2.x = r1.x + r1.width * 0.3
                r2.y = r1.y + r1.depth * 0.3

        elif violation_type == "tiny_room":
            if plan.rooms:
                room = random.choice(plan.rooms)
                room.width = 0.8
                room.depth = 0.8

        elif violation_type == "no_bathroom":
            plan.rooms = [r for r in plan.rooms if r.type != "bathroom"]

        elif violation_type == "no_entrance":
            plan.rooms = [r for r in plan.rooms if r.type != "entrance"]

        return plan

    def generate_batch(
        self,
        batch_size: int,
        valid_ratio: float = 0.7,
        min_rooms: int = 3,
        max_rooms: int = 8,
    ) -> Iterator[FloorPlan]:
        for _ in range(batch_size):
            num_rooms = random.randint(min_rooms, max_rooms)
            is_valid = random.random() < valid_ratio
            yield self.generate(num_rooms=num_rooms, valid=is_valid)
