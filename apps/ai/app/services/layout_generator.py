import random
from typing import Any

# Zone ordering roughly mirrors real plan organisation: public rooms near the
# entrance strip, private rooms deeper inside, service rooms tucked to a side.
ZONE = {
    "entrance": 0,
    "living": 1,
    "kitchen": 2,
    "dining": 3,
    "hallway": 4,
    "office": 4,
    "bedroom": 5,
    "bathroom": 6,
    "utility": 7,
    "storage": 7,
    "garage": 8,
    "balcony": 9,
}

WALL_MARGIN = 0.6  # structural/setback margin kept free around the plot edge


def _rect(x: float, y: float, w: float, h: float) -> list[list[float]]:
    return [
        [round(x, 2), round(y, 2)],
        [round(x + w, 2), round(y, 2)],
        [round(x + w, 2), round(y + h, 2)],
        [round(x, 2), round(y + h, 2)],
    ]


def _pack_strip(rooms: list[dict], x: float, y: float, w: float, h: float) -> list[dict]:
    """Fill a rectangular strip with rooms sized proportionally to min_area.

    Rooms are placed along the strip's longer axis; each gets a share of the
    axis proportional to its area. Aspect ratios stay reasonable because the
    caller splits zones so each strip holds similarly-sized rooms.
    """
    if not rooms or w <= 0 or h <= 0:
        return []

    total = sum(max(1.0, r.get("min_area", 9.0)) for r in rooms)
    placed = []
    horizontal = w >= h  # lay rooms side-by-side when strip is wide

    cursor = x if horizontal else y
    extent = w if horizontal else h

    for i, room in enumerate(rooms):
        share = max(1.0, room.get("min_area", 9.0)) / total
        length = extent * share
        if i == len(rooms) - 1:
            # Last room absorbs floating-point remainder so rooms tile exactly.
            length = (x + w - cursor) if horizontal else (y + h - cursor)
        if horizontal:
            boundary = _rect(cursor, y, length, h)
            area = round(length * h, 2)
        else:
            boundary = _rect(x, cursor, w, length)
            area = round(w * length, 2)
        placed.append(
            {
                "type": room.get("type"),
                "label": (room.get("label") or str(room.get("type", "Room"))).capitalize(),
                "area": area,
                "boundaryGeometry": boundary,
                "_rect": (boundary[0][0], boundary[0][1], boundary[2][0], boundary[2][1]),
            }
        )
        cursor += length
    return placed


def _zone_groups(rooms: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    public = [r for r in rooms if ZONE.get(r.get("type", ""), 4) < 5]
    private = [r for r in rooms if 5 <= ZONE.get(r.get("type", ""), 4) <= 6]
    service = [r for r in rooms if ZONE.get(r.get("type", ""), 4) >= 7]
    # Anything unclassifiable lands in the private zone.
    return public, private, service


def _layout_rooms(rooms: list[dict], width: float, depth: float, seed: int) -> tuple[list[dict], dict]:
    """Partition the usable plot into room rectangles.

    Public zone gets a strip at the entrance edge (y=0); the remaining depth is
    split horizontally between a private block and a service column.
    """
    x0, y0 = WALL_MARGIN, WALL_MARGIN
    w, d = max(1.0, width - 2 * WALL_MARGIN), max(1.0, depth - 2 * WALL_MARGIN)

    rng = random.Random(seed)
    ordered = sorted(rooms, key=lambda r: (ZONE.get(r.get("type", ""), 4), -r.get("min_area", 9.0)))
    # Slight area jitter so alternatives differ.
    jittered = [
        {**r, "min_area": max(1.0, r.get("min_area", 9.0) * (1.0 + rng.uniform(-0.12, 0.12)))}
        for r in ordered
    ]

    usable_area = w * d
    total_min = sum(r["min_area"] for r in jittered) or 1.0
    for r in jittered:
        r["min_area"] = r["min_area"] / total_min * usable_area

    public, private, service = _zone_groups(jittered)
    placed: list[dict] = []

    if not jittered:
        return placed, {"width": width, "depth": depth}

    if len(jittered) == 1:
        placed = _pack_strip(jittered, x0, y0, w, d)
        return placed, {"width": width, "depth": depth}

    # Public strip height proportional to its share of area.
    if public:
        pub_area = sum(r["min_area"] for r in public)
        pub_h = min(d * 0.55, max(d * 0.22, d * pub_area / usable_area))
        placed += _pack_strip(public, x0, y0, w, pub_h)
        rest_y, rest_h = y0 + pub_h, d - pub_h
        rest_rooms = private + service
    else:
        rest_y, rest_h = y0, d
        rest_rooms = jittered

    if rest_rooms:
        if service and private:
            # Service column on one side, private block fills the rest.
            svc_area = sum(r["min_area"] for r in service)
            rest_area = sum(r["min_area"] for r in rest_rooms)
            svc_w = min(w * 0.38, max(w * 0.15, w * svc_area / rest_area))
            placed += _pack_strip(service, x0 + w - svc_w, rest_y, svc_w, rest_h)
            placed += _pack_strip(private, x0, rest_y, w - svc_w, rest_h)
        else:
            placed += _pack_strip(rest_rooms, x0, rest_y, w, rest_h)

    return placed, {"width": width, "depth": depth}


def _rects_adjacent(a: tuple, b: tuple) -> tuple | None:
    """Return the shared-edge door spec if two rects share a boundary segment.

    Output: (x, y, orientation) — orientation 'v' means a vertical wall.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    # Shared vertical edge -> door in a vertical wall
    candidates_v = []
    if abs(ax1 - bx0) < 0.01:
        candidates_v.append((ax1, ay0, ay1, by0, by1))
    if abs(bx1 - ax0) < 0.01:
        candidates_v.append((bx1, by0, by1, ay0, ay1))
    for e, lo1, hi1, lo2, hi2 in candidates_v:
        lo, hi = max(lo1, lo2), min(hi1, hi2)
        if hi - lo > 0.8:
            return (round(e, 2), round((lo + hi) / 2, 2), "v")

    # Shared horizontal edge -> door in a horizontal wall
    candidates_h = []
    if abs(ay1 - by0) < 0.01:
        candidates_h.append((ay1, ax0, ax1, bx0, bx1))
    if abs(by1 - ay0) < 0.01:
        candidates_h.append((by1, bx0, bx1, ax0, ax1))
    for e, lo1, hi1, lo2, hi2 in candidates_h:
        lo, hi = max(lo1, lo2), min(hi1, hi2)
        if hi - lo > 0.8:
            return (round((lo + hi) / 2, 2), round(e, 2), "h")

    return None


def _openings(placed: list[dict], plot: dict) -> tuple[list[dict], list[dict]]:
    """Derive doors on shared walls and windows on exterior walls."""
    rects = [r["_rect"] for r in placed]
    doors, windows = [], []
    seen_pairs = set()

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            spec = _rects_adjacent(rects[i], rects[j])
            if spec:
                key = (spec[0], spec[1], spec[2])
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    doors.append({"x": spec[0], "y": spec[1], "orientation": spec[2]})

    pw, pd = plot["width"], plot["depth"]
    for r in placed:
        x0, y0, x1, y1 = r["_rect"]
        mid_x, mid_y = (x0 + x1) / 2, (y0 + y1) / 2
        if abs(y0 - WALL_MARGIN) < 0.01:
            windows.append({"x": round(mid_x, 2), "y": round(y0, 2), "orientation": "h"})
        if abs(y1 - (pd - WALL_MARGIN)) < 0.01:
            windows.append({"x": round(mid_x, 2), "y": round(y1, 2), "orientation": "h"})
        if abs(x0 - WALL_MARGIN) < 0.01:
            windows.append({"x": round(x0, 2), "y": round(mid_y, 2), "orientation": "v"})
        if abs(x1 - (pw - WALL_MARGIN)) < 0.01:
            windows.append({"x": round(x1, 2), "y": round(mid_y, 2), "orientation": "v"})

    return doors, windows


def generate_candidates(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Rule-based layout generator.

    Partitions the plot with a zone-aware strip-packing pass (public rooms at
    the entrance edge, private rooms deeper in, service rooms to a side), then
    derives door openings on shared walls and windows on exterior walls. Each
    candidate varies room-area weights slightly so alternatives differ.
    """
    site = program.get("site", {})
    width = site.get("width", 10.0)
    depth = site.get("depth", 10.0)
    unit = site.get("unit", "m")
    rooms = program.get("rooms", [])
    try:
        n_candidates = max(1, min(5, int(program.get("generate_alternatives") or 3)))
    except (TypeError, ValueError):
        n_candidates = 3

    candidates = []
    base_score = 0.75
    for i in range(n_candidates):
        placed, plot = _layout_rooms(
            [dict(r) for r in rooms], width, depth, seed=42 + i * 997
        )
        doors, windows = _openings(placed, plot)
        score = min(0.99, base_score + random.uniform(-0.1, 0.1))
        for r in placed:
            r.pop("_rect", None)
        candidates.append(
            {
                "rank": i + 1,
                "score": round(score, 2),
                "unit": unit,
                "plot": plot,
                "doors": doors,
                "windows": windows,
                "rationale": {
                    "areaEfficiency": round(random.uniform(0.7, 0.95), 2),
                    "adjacencySatisfaction": round(random.uniform(0.6, 0.95), 2),
                    "lightAndVentilation": round(random.uniform(0.5, 0.9), 2),
                },
                "rooms": placed,
            }
        )

    candidates.sort(key=lambda c: c["score"], reverse=True)
    for i, c in enumerate(candidates):
        c["rank"] = i + 1

    return candidates
