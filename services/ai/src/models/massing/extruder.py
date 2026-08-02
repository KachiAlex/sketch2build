"""3D massing / extrusion pipeline.

Converts 2D floor plan room polygons into 3D volumetric geometry.
Extrudes walls, floors, ceilings, doors, and windows from structured room data.
"""

import structlog
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import cv2

logger = structlog.get_logger()


@dataclass
class Wall3D:
    """A 3D wall segment with openings (doors/windows)."""
    x1: float
    y1: float
    z1: float
    x2: float
    y2: float
    z2: float
    thickness: float = 0.15
    height: float = 2.7
    openings: list[dict] = field(default_factory=list)
    id: str = ""


@dataclass
class Room3D:
    """A 3D extruded room with walls, floor, ceiling."""
    type: str
    room_id: str
    x: float
    y: float
    z: float = 0.0
    width: float = 0.0
    depth: float = 0.0
    height: float = 2.7
    walls: list[Wall3D] = field(default_factory=list)
    floor_vertices: list[tuple[float, float, float]] = field(default_factory=list)
    ceiling_vertices: list[tuple[float, float, float]] = field(default_factory=list)
    openings: list[dict] = field(default_factory=list)

    @property
    def volume(self) -> float:
        return self.width * self.depth * self.height

    @property
    def floor_area(self) -> float:
        return self.width * self.depth


@dataclass
class Building3D:
    """Complete 3D building model from floor plan."""
    rooms: list[Room3D] = field(default_factory=list)
    floors: list[dict] = field(default_factory=list)
    wall_color: str = "#e8e0d0"
    floor_color: str = "#c0a080"
    ceiling_color: str = "#f0f0f0"

    def to_glb_dict(self) -> dict[str, Any]:
        """Export as a GLB-compatible JSON dictionary (gltf2-compatible)."""
        vertices = []
        indices = []
        vertex_offset = 0

        for room in self.rooms:
            # Floor vertices
            floor_verts = room.floor_vertices if room.floor_vertices else [
                (room.x, room.y, room.z),
                (room.x + room.width, room.y, room.z),
                (room.x + room.width, room.y + room.depth, room.z),
                (room.x, room.y + room.depth, room.z),
            ]
            vertices.extend(floor_verts)
            indices.extend([
                vertex_offset + 0, vertex_offset + 1, vertex_offset + 2,
                vertex_offset + 0, vertex_offset + 2, vertex_offset + 3,
            ])
            vertex_offset += len(floor_verts)

            # Ceiling vertices
            ceiling_verts = room.ceiling_vertices if room.ceiling_vertices else [
                (room.x, room.y, room.z + room.height),
                (room.x + room.width, room.y, room.z + room.height),
                (room.x + room.width, room.y + room.depth, room.z + room.height),
                (room.x, room.y + room.depth, room.z + room.height),
            ]
            vertices.extend(ceiling_verts)
            indices.extend([
                vertex_offset + 0, vertex_offset + 2, vertex_offset + 1,
                vertex_offset + 0, vertex_offset + 3, vertex_offset + 2,
            ])
            vertex_offset += len(ceiling_verts)

        return {
            "vertices": vertices,
            "indices": indices,
            "room_count": len(self.rooms),
            "total_volume": sum(r.volume for r in self.rooms),
            "total_floor_area": sum(r.floor_area for r in self.rooms),
        }


class FloorPlanExtruder:
    """Extrudes 2D floor plan rooms into 3D geometry."""

    DEFAULT_WALL_HEIGHT = 2.7    # meters
    DEFAULT_WALL_THICKNESS = 0.15  # meters
    DEFAULT_FLOOR_THICKNESS = 0.15
    DEFAULT_CEILING_THICKNESS = 0.12

    # Room type specific heights (meters)
    ROOM_HEIGHTS = {
        "living": 2.7,
        "kitchen": 2.5,
        "bedroom": 2.7,
        "bathroom": 2.4,
        "dining": 2.7,
        "hallway": 2.5,
        "entrance": 2.7,
        "storage": 2.5,
        "garage": 2.8,
        "office": 2.7,
        "utility": 2.5,
        "balcony": 2.5,
    }

    def __init__(
        self,
        wall_height: float | None = None,
        wall_thickness: float | None = None,
    ):
        self.wall_height = wall_height or self.DEFAULT_WALL_HEIGHT
        self.wall_thickness = wall_thickness or self.DEFAULT_WALL_THICKNESS

    def extrude_room(
        self,
        room_type: str,
        x: float,
        y: float,
        width: float,
        depth: float,
        room_id: str = "",
        adjacency_info: list[tuple[float, float, float, float]] | None = None,
    ) -> Room3D:
        """Extrude a single room into 3D geometry."""
        height = self.ROOM_HEIGHTS.get(room_type, self.wall_height)

        # Floor vertices (counter-clockwise)
        floor_vertices = [
            (x, y, 0.0),
            (x + width, y, 0.0),
            (x + width, y + depth, 0.0),
            (x, y + depth, 0.0),
        ]

        # Ceiling vertices
        ceiling_vertices = [
            (x, y, height),
            (x + width, y, height),
            (x + width, y + depth, height),
            (x, y + depth, height),
        ]

        # Build walls with openings
        walls = []
        wall_segments = [
            ((x, y), (x + width, y)),           # bottom
            ((x + width, y), (x + width, y + depth)),  # right
            ((x + width, y + depth), (x, y + depth)),   # top
            ((x, y + depth), (x, y)),           # left
        ]

        for i, ((x1, y1), (x2, y2)) in enumerate(wall_segments):
            wall = Wall3D(
                x1=x1, y1=y1, z1=0.0,
                x2=x2, y2=y2, z2=height,
                thickness=self.wall_thickness,
                height=height,
                id=f"wall_{room_id}_{i}",
            )
            walls.append(wall)

        # Add openings (doors) for adjacencies
        openings = []
        if adjacency_info:
            for adj_x, adj_y, adj_w, adj_d in adjacency_info:
                # Simple door opening at shared wall midpoint
                door_x = min(adj_x + adj_w / 2, x + width)
                door_y = min(adj_y + adj_d / 2, y + depth)
                openings.append({
                    "type": "door",
                    "x": door_x, "y": door_y,
                    "width": 0.9, "height": 2.1,
                    "wall_id": "",
                })

        return Room3D(
            type=room_type,
            room_id=room_id,
            x=x, y=y, z=0.0,
            width=width, depth=depth, height=height,
            walls=walls,
            floor_vertices=floor_vertices,
            ceiling_vertices=ceiling_vertices,
            openings=openings,
        )

    def extrude_floor_plan(
        self,
        rooms: list[dict[str, Any]],
        adjacency: list[tuple[int, int]] = None,
        entrance_position: tuple[float, float] | None = None,
    ) -> Building3D:
        """Extrude an entire floor plan into 3D geometry."""
        building = Building3D()
        adjacency = adjacency or []

        for i, room_data in enumerate(rooms):
            room_type = room_data.get("type", "living")
            x = room_data.get("x", 0.0)
            y = room_data.get("y", 0.0)
            width = room_data.get("w", room_data.get("width", 4.0))
            depth = room_data.get("d", room_data.get("depth", 4.0))
            room_id = room_data.get("id", f"room_{i}")

            # Find adjacent rooms for door placement
            adj_info = []
            for a, b in adjacency:
                if a == i and b < len(rooms):
                    adj_room = rooms[b]
                    adj_info.append((
                        adj_room.get("x", 0.0),
                        adj_room.get("y", 0.0),
                        adj_room.get("w", adj_room.get("width", 4.0)),
                        adj_room.get("d", adj_room.get("depth", 4.0)),
                    ))
                elif b == i and a < len(rooms):
                    adj_room = rooms[a]
                    adj_info.append((
                        adj_room.get("x", 0.0),
                        adj_room.get("y", 0.0),
                        adj_room.get("w", adj_room.get("width", 4.0)),
                        adj_room.get("d", adj_room.get("depth", 4.0)),
                    ))

            room_3d = self.extrude_room(
                room_type=room_type,
                x=x, y=y,
                width=width, depth=depth,
                room_id=room_id,
                adjacency_info=adj_info,
            )
            building.rooms.append(room_3d)

        # Add entrance door
        if entrance_position:
            building.floors.append({
                "level": 0,
                "entrance": {
                    "x": entrance_position[0],
                    "y": entrance_position[1],
                    "z": 0.0,
                    "type": "entrance_door",
                    "width": 1.0,
                    "height": 2.1,
                },
            })

        logger.info(
            "Floor plan extruded to 3D",
            rooms=len(building.rooms),
            total_volume=sum(r.volume for r in building.rooms),
            total_area=sum(r.floor_area for r in building.rooms),
        )
        return building

    def generate_3d_preview_image(
        self,
        building: Building3D,
        size: int = 512,
        view: str = "axonometric",
    ) -> Image.Image:
        """Generate a 2D preview image from the 3D model (axonometric projection)."""
        img = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(img)

        # Axonometric projection: 30° tilt, 45° rotation
        scale = size / 30.0  # assume max 30m
        offset_x = size / 2
        offset_y = size / 4

        def project_iso(x: float, y: float, z: float) -> tuple[float, float]:
            """Isometric projection to 2D."""
            px = (x - y) * np.cos(np.pi / 6) * scale + offset_x
            py = (x + y) * np.sin(np.pi / 6) * scale - z * scale + offset_y
            return px, py

        # Draw room floors (colored by type)
        ROOM_COLORS = {
            "living": (230, 210, 180),
            "kitchen": (255, 240, 200),
            "bedroom": (220, 240, 220),
            "bathroom": (200, 230, 255),
            "dining": (255, 235, 205),
            "hallway": (240, 240, 240),
            "entrance": (255, 230, 210),
            "storage": (210, 210, 210),
            "garage": (200, 200, 200),
            "office": (255, 240, 220),
            "utility": (220, 220, 220),
            "balcony": (210, 230, 240),
        }

        for room in building.rooms:
            color = ROOM_COLORS.get(room.type, (240, 240, 240))
            # Draw floor
            verts = room.floor_vertices
            if verts:
                screen_verts = [project_iso(v[0], v[1], v[2]) for v in verts]
                draw.polygon(screen_verts, fill=color, outline="black")

            # Draw walls (top edges)
            if verts:
                top_verts = [project_iso(v[0], v[1], room.height) for v in verts]
                draw.polygon(top_verts, outline="gray", fill=None)
                # Connect floor to ceiling edges
                for i in range(len(verts)):
                    i2 = (i + 1) % len(verts)
                    draw.line([screen_verts[i], top_verts[i]], fill="gray", width=1)

        return img


class MultiStoryExtruder:
    """Extrude multiple floors into a 3D building model."""

    def __init__(self, base_extruder: FloorPlanExtruder | None = None):
        self.extruder = base_extruder or FloorPlanExtruder()

    def extrude_building(
        self,
        floors: list[list[dict[str, Any]]],
        floor_heights: list[float] | None = None,
        adjacency_per_floor: list[list[tuple[int, int]]] | None = None,
    ) -> Building3D:
        """Extrude a multi-story building."""
        building = Building3D()
        current_z = 0.0

        for floor_idx, floor_rooms in enumerate(floors):
            adjacency = adjacency_per_floor[floor_idx] if adjacency_per_floor else None
            floor_height = floor_heights[floor_idx] if floor_heights else 3.0

            floor_building = self.extruder.extrude_floor_plan(
                rooms=floor_rooms,
                adjacency=adjacency,
            )

            # Offset rooms by current Z
            for room in floor_building.rooms:
                room.z = current_z
                room.ceiling_vertices = [
                    (v[0], v[1], v[2] + current_z) for v in room.ceiling_vertices
                ]
                room.floor_vertices = [
                    (v[0], v[1], v[2] + current_z) for v in room.floor_vertices
                ]
                # Offset wall z values
                for wall in room.walls:
                    wall.z1 += current_z
                    wall.z2 += current_z
                room.height = floor_height

            building.rooms.extend(floor_building.rooms)
            building.floors.append({
                "level": floor_idx,
                "height": floor_height,
                "room_count": len(floor_rooms),
                "z_base": current_z,
                "z_top": current_z + floor_height,
            })

            current_z += floor_height + self.extruder.DEFAULT_FLOOR_THICKNESS

        logger.info(
            "Multi-story building extruded",
            floors=len(floors),
            total_rooms=len(building.rooms),
            total_height=current_z,
        )
        return building
