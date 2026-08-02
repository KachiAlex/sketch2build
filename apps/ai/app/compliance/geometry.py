from __future__ import annotations
from typing import List, Tuple
from dataclasses import dataclass

Point = Tuple[float, float]
Polygon = List[Point]


@dataclass
class Rect:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @staticmethod
    def from_polygon(poly: Polygon) -> "Rect":
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        return Rect(min(xs), min(ys), max(xs), max(ys))

    def width(self) -> float:
        return self.x_max - self.x_min

    def depth(self) -> float:
        return self.y_max - self.y_min

    def area(self) -> float:
        return self.width() * self.depth()


def polygon_area(poly: Polygon) -> float:
    """Shoelace formula for polygon area."""
    n = len(poly)
    area = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def rects_intersect(a: Rect, b: Rect) -> bool:
    return not (
        a.x_max <= b.x_min
        or a.x_min >= b.x_max
        or a.y_max <= b.y_min
        or a.y_min >= b.y_max
    )


def detect_overlaps(room_boundaries: List[Polygon]) -> List[Tuple[int, int]]:
    """Return pairs of indices of rooms whose bounding boxes overlap (excluding shared walls)."""
    rects = [Rect.from_polygon(poly) for poly in room_boundaries]
    overlaps: List[Tuple[int, int]] = []
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if rects_intersect(rects[i], rects[j]):
                # Exclude touching-only cases
                if (
                    rects[i].x_max > rects[j].x_min
                    and rects[j].x_max > rects[i].x_min
                    and rects[i].y_max > rects[j].y_min
                    and rects[j].y_max > rects[i].y_min
                ):
                    overlaps.append((i, j))
    return overlaps


def check_setback(site: Polygon, building: Polygon, required: float) -> bool:
    """Simplified setback check for axis-aligned rectangular sites and buildings."""
    site_rect = Rect.from_polygon(site)
    building_rect = Rect.from_polygon(building)
    return (
        building_rect.x_min >= site_rect.x_min + required
        and building_rect.x_max <= site_rect.x_max - required
        and building_rect.y_min >= site_rect.y_min + required
        and building_rect.y_max <= site_rect.y_max - required
    )


def build_room_graph(room_boundaries: List[Polygon], tolerance: float = 0.5) -> List[List[int]]:
    """Build adjacency graph where edges connect rooms sharing a wall segment."""
    n = len(room_boundaries)
    graph: List[List[int]] = [[] for _ in range(n)]
    rects = [Rect.from_polygon(poly) for poly in room_boundaries]

    for i in range(n):
        for j in range(i + 1, n):
            a, b = rects[i], rects[j]
            # Share a vertical wall
            if abs(a.x_max - b.x_min) < tolerance or abs(b.x_max - a.x_min) < tolerance:
                if a.y_min < b.y_max and b.y_min < a.y_max:
                    graph[i].append(j)
                    graph[j].append(i)
            # Share a horizontal wall
            if abs(a.y_max - b.y_min) < tolerance or abs(b.y_max - a.y_min) < tolerance:
                if a.x_min < b.x_max and b.x_min < a.x_max:
                    graph[i].append(j)
                    graph[j].append(i)
    return graph


def all_rooms_reachable(graph: List[List[int]], entrance_index: int = 0) -> bool:
    """BFS reachability from an assumed entrance room index."""
    visited = {entrance_index}
    queue = [entrance_index]
    while queue:
        node = queue.pop(0)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return len(visited) == len(graph)
