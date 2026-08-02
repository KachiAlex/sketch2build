import math
from typing import List, Tuple

Point = Tuple[float, float]
Segment = Tuple[Point, Point]


def snap_to_right_angle(p1: Point, p2: Point) -> Point:
    """Snap a free-form end point so the segment is axis-aligned if close."""
    x1, y1 = p1
    x2, y2 = p2
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    threshold = max(dx, dy) * 0.15  # 15% tolerance

    if abs(dx - dy) < threshold:
        # Keep diagonal roughly as-is, snap to 45 deg by averaging distance
        dist = (dx + dy) / 2
        x_dir = 1 if x2 >= x1 else -1
        y_dir = 1 if y2 >= y1 else -1
        return (x1 + x_dir * dist, y1 + y_dir * dist)

    if dx < threshold:
        return (x1, y2)
    if dy < threshold:
        return (x2, y1)

    return (x2, y2)


def snap_segments_to_grid(segments: List[Segment], grid_size: float = 0.05) -> List[Segment]:
    """Round each segment endpoint to a metric/imperial grid module."""
    snapped: List[Segment] = []
    for p1, p2 in segments:
        sp1 = _snap_point(p1, grid_size)
        sp2 = _snap_point(p2, grid_size)
        # Re-run right-angle snapping on the gridded segment
        sp2 = snap_to_right_angle(sp1, sp2)
        snapped.append((sp1, sp2))
    return snapped


def _snap_point(point: Point, grid_size: float) -> Point:
    return (
        round(point[0] / grid_size) * grid_size,
        round(point[1] / grid_size) * grid_size,
    )


def filter_duplicate_segments(segments: List[Segment], tolerance: float = 1e-3) -> List[Segment]:
    """Remove near-duplicate wall segments."""
    unique: List[Segment] = []
    for seg in segments:
        if not _has_duplicate(seg, unique, tolerance):
            unique.append(seg)
    return unique


def _has_duplicate(seg: Segment, existing: List[Segment], tolerance: float) -> bool:
    a1, a2 = seg
    for b1, b2 in existing:
        if (
            _close(a1, b1, tolerance) and _close(a2, b2, tolerance)
        ) or (
            _close(a1, b2, tolerance) and _close(a2, b1, tolerance)
        ):
            return True
    return False


def _close(a: Point, b: Point, tolerance: float) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) < tolerance
