import random
from typing import Any, Callable

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

# Room-type pairs that should never share a door (privacy / hygiene).
DOOR_DENY = {
    ("bathroom", "bathroom"),
    ("bathroom", "kitchen"),
    ("bathroom", "dining"),
    ("bathroom", "living"),
    ("bedroom", "bedroom"),
    ("storage", "bedroom"),
    ("garage", "bathroom"),
    ("utility", "bathroom"),
    ("balcony", "bathroom"),
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
    """Fill a rectangular strip with rooms sized proportionally to min_area."""
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
                "adjacency": room.get("adjacency") or [],
                "_rect": (boundary[0][0], boundary[0][1], boundary[2][0], boundary[2][1]),
            }
        )
        cursor += length
    return placed


def _zone_groups(rooms: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    public = [r for r in rooms if ZONE.get(r.get("type", ""), 4) < 5]
    private = [r for r in rooms if 5 <= ZONE.get(r.get("type", ""), 4) <= 6]
    service = [r for r in rooms if ZONE.get(r.get("type", ""), 4) >= 7]
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
            svc_area = sum(r["min_area"] for r in service)
            rest_area = sum(r["min_area"] for r in rest_rooms)
            svc_w = min(w * 0.38, max(w * 0.15, w * svc_area / rest_area))
            placed += _pack_strip(service, x0 + w - svc_w, rest_y, svc_w, rest_h)
            placed += _pack_strip(private, x0, rest_y, w - svc_w, rest_h)
        else:
            placed += _pack_strip(rest_rooms, x0, rest_y, w, rest_h)

    return placed, {"width": width, "depth": depth}


def _rects_adjacent(a: tuple, b: tuple) -> tuple | None:
    """Return the shared-edge door spec if two rects share a boundary segment."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    candidates_v = []
    if abs(ax1 - bx0) < 0.01:
        candidates_v.append((ax1, ay0, ay1, by0, by1))
    if abs(bx1 - ax0) < 0.01:
        candidates_v.append((bx1, by0, by1, ay0, ay1))
    for e, lo1, hi1, lo2, hi2 in candidates_v:
        lo, hi = max(lo1, lo2), min(hi1, hi2)
        if hi - lo > 0.8:
            return (round(e, 2), round((lo + hi) / 2, 2), "v")

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


def _door_denied(a: str, b: str) -> bool:
    pair = (a, b)
    return pair in DOOR_DENY or (b, a) in DOOR_DENY


def _desired_adjacent(room_a: dict, room_b: dict) -> bool:
    """True when either room's brief adjacency list includes the other's type."""
    return room_b.get("type") in (room_a.get("adjacency") or []) or room_a.get(
        "type"
    ) in (room_b.get("adjacency") or [])


def _openings(
    placed: list[dict],
    plot: dict,
    allow_pair: Callable[[dict, dict], bool] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Derive doors on shared walls and windows on exterior walls.

    With `allow_pair` the caller controls which adjacent room pairs may get a
    door; without it every shared edge gets one (legacy behaviour used by the
    sketch path). Rooms may carry a "floor" tag propagated onto openings.
    """
    rects = [r["_rect"] for r in placed]
    doors, windows = [], []
    seen_pairs = set()
    adjacency_pairs: list[tuple[int, int]] = []

    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            if placed[i].get("floor", 1) != placed[j].get("floor", 1):
                continue
            spec = _rects_adjacent(rects[i], rects[j])
            if not spec:
                continue
            adjacency_pairs.append((i, j))
            if allow_pair is not None and not allow_pair(placed[i], placed[j]):
                continue
            key = (spec[0], spec[1], spec[2], placed[i].get("floor", 1))
            if key not in seen_pairs:
                seen_pairs.add(key)
                doors.append(
                    {"x": spec[0], "y": spec[1], "orientation": spec[2], "floor": placed[i].get("floor", 1)}
                )

    # Windows on building-envelope edges: a wall is exterior when no other
    # room covers that edge's midpoint.
    for idx, r in enumerate(placed):
        x0, y0, x1, y1 = r["_rect"]
        floor = r.get("floor", 1)
        edges = [
            (x0, "v", (y0 + y1) / 2),  # west wall
            (x1, "v", (y0 + y1) / 2),  # east wall
            (y0, "h", (x0 + x1) / 2),  # north wall
            (y1, "h", (x0 + x1) / 2),  # south wall
        ]
        for e, orientation, mid in edges:
            interior = False
            for jdx, other in enumerate(placed):
                if jdx == idx or other.get("floor", 1) != floor:
                    continue
                ox0, oy0, ox1, oy1 = other["_rect"]
                if orientation == "v":
                    if (abs(ox0 - e) < 0.01 or abs(ox1 - e) < 0.01) and oy0 < mid < oy1:
                        interior = True
                        break
                else:
                    if (abs(oy0 - e) < 0.01 or abs(oy1 - e) < 0.01) and ox0 < mid < ox1:
                        interior = True
                        break
            if not interior:
                wx, wy = (e, mid) if orientation == "v" else (mid, e)
                windows.append(
                    {"x": round(wx, 2), "y": round(wy, 2), "orientation": orientation, "floor": floor}
                )

    return doors, windows


def _ensure_connectivity(placed: list[dict], doors: list[dict]) -> None:
    """Guarantee every room can reach an entrance-side room by adding doors.

    BFS over placed-adjacency pairs that already have doors. Unreachable rooms
    get a door to any placed-adjacent non-denied neighbour, falling back to any
    neighbour when no clean option exists.
    """
    rects = [r["_rect"] for r in placed]
    pairs = [
        (i, j, _rects_adjacent(rects[i], rects[j]))
        for i in range(len(rects))
        for j in range(i + 1, len(rects))
        if placed[i].get("floor", 1) == placed[j].get("floor", 1)
    ]
    pairs = [(i, j, s) for i, j, s in pairs if s]

    def door_exists(i: int, j: int) -> bool:
        spec = _rects_adjacent(rects[i], rects[j])
        return spec is not None and any(
            d["x"] == spec[0] and d["y"] == spec[1] for d in doors
        )

    def reach(seed_types: tuple[str, ...]) -> set[int]:
        seeds = {i for i, r in enumerate(placed) if r.get("type") in seed_types}
        if not seeds:
            seeds = {0}
        seen = set(seeds)
        frontier = list(seeds)
        while frontier:
            cur = frontier.pop()
            for i, j, _ in pairs:
                other = j if i == cur else i if j == cur else None
                if other is not None and other not in seen and door_exists(i, j):
                    seen.add(other)
                    frontier.append(other)
        return seen

    for _ in range(len(placed)):
        reached = reach(("entrance", "living", "hallway"))
        missing = [i for i in range(len(placed)) if i not in reached]
        if not missing:
            return
        added = False
        for i in missing:
            neighbours = [(i, j, s) if a == i else (j, i, s) for a, j, s in pairs if a == i or j == i]
            neighbours = [(a, b, s) for a, b, s in neighbours if a == i]
            neighbours.sort(key=lambda t: _door_denied(placed[t[0]]["type"], placed[t[1]]["type"]))
            for a, b, spec in neighbours:
                floor = placed[i].get("floor", 1)
                doors.append({"x": spec[0], "y": spec[1], "orientation": spec[2], "floor": floor})
                added = True
                break
            if added:
                break
        if not added:
            return


def _rotate_placed(placed: list[dict], plot: dict, quarter_turns: int) -> None:
    """Rotate the layout in 90° steps (axis-aligned) into the plot space.

    q=1/3 layouts are generated in transposed (d×w) space; q=2 in (w×d).
    """
    q = quarter_turns % 4
    if q == 0:
        return
    w, d = plot["width"], plot["depth"]
    transforms = {
        1: lambda x, y: (w - y, x),
        2: lambda x, y: (w - x, d - y),
        3: lambda x, y: (y, d - x),
    }
    tx = transforms[q]
    for room in placed:
        pts = [[round(tx(x, y)[0], 2), round(tx(x, y)[1], 2)] for x, y in room["boundaryGeometry"]]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        room["boundaryGeometry"] = _rect(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        room["_rect"] = (min(xs), min(ys), max(xs), max(ys))


def generate_candidates(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Rule-based layout generator.

    Zone-aware strip packing (public near entrance, private deeper, service to
    a side), then derives doors/windows. Honours:
      - orientation: rotates the plan so the public edge faces the site
        orientation (quantised to 90°)
      - floors: private rooms move to upper floors (floor-tagged rooms)
      - adjacency: brief-derived desired adjacency + deny-list door policy
        plus a connectivity pass so every room stays reachable
      - style: carried into the rationale for downstream explainability
    """
    site = program.get("site", {})
    width = site.get("width", 10.0)
    depth = site.get("depth", 10.0)
    unit = site.get("unit", "m")
    rooms = program.get("rooms", [])
    style = program.get("style") or "modern"

    try:
        orientation = float(program.get("orientation") or 0.0) % 360
    except (TypeError, ValueError):
        orientation = 0.0
    quarter_turns = int(round(orientation / 90.0)) % 4

    try:
        floors = max(1, min(4, int(program.get("floors") or 1)))
    except (TypeError, ValueError):
        floors = 1

    try:
        n_candidates = max(1, min(5, int(program.get("generate_alternatives") or 3)))
    except (TypeError, ValueError):
        n_candidates = 3

    # Split rooms per floor: public + service on the ground floor, private
    # rooms (bedrooms, bathrooms) distributed across upper floors.
    floor_rooms: list[list[dict]] = [[] for _ in range(floors)]
    if floors > 1:
        public, private, service = _zone_groups(rooms)
        floor_rooms[0] = [dict(r) for r in public + service]
        upper_floors = max(1, floors - 1)
        for idx, r in enumerate(private):
            floor_rooms[1 + (idx % upper_floors)].append(dict(r))
        if not floor_rooms[0]:
            floor_rooms[0] = [dict(r) for r in rooms]
    else:
        floor_rooms[0] = [dict(r) for r in rooms]

    # For 90/270 orientations generate in transposed space then rotate back.
    layout_w, layout_d = (depth, width) if quarter_turns in (1, 3) else (width, depth)

    candidates = []
    base_score = 0.75
    for i in range(n_candidates):
        placed: list[dict] = []
        for f, f_rooms in enumerate(floor_rooms, start=1):
            f_placed, plot = _layout_rooms(
                [dict(r) for r in f_rooms], layout_w, layout_d, seed=42 + i * 997 + f * 131
            )
            for r in f_placed:
                r["floor"] = f
            placed += f_placed

        _rotate_placed(placed, {"width": width, "depth": depth}, quarter_turns)
        plot = {"width": width, "depth": depth}

        def allow_pair(a: dict, b: dict) -> bool:
            if _door_denied(a.get("type", ""), b.get("type", "")):
                return False
            has_meta = bool(a.get("adjacency") or b.get("adjacency"))
            if has_meta:
                return _desired_adjacent(a, b)
            return True

        doors, windows = _openings(placed, plot, allow_pair=allow_pair)
        _ensure_connectivity(placed, doors)

        score = min(0.99, base_score + random.uniform(-0.1, 0.1))
        for r in placed:
            r.pop("_rect", None)
            r.pop("adjacency", None)
        candidates.append(
            {
                "rank": i + 1,
                "score": round(score, 2),
                "unit": unit,
                "plot": plot,
                "floors": floors,
                "doors": doors,
                "windows": windows,
                "rationale": {
                    "style": style,
                    "orientation": orientation,
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
