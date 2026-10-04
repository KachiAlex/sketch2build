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

WALL_MARGIN = 0.6  # structural margin kept free inside the build envelope


def _layout_margins(q: int, setbacks: dict) -> tuple[float, float, float, float]:
    """Map site setbacks into layout-space margins (left, bottom, right, top).

    The generator always packs with the public/entrance strip at layout y=0,
    then rotates by `q` quarter-turns. So the "front" setback must land on
    whichever layout edge becomes the site's bottom edge after rotation.
    """
    f = float(setbacks.get("front") or 0)
    s = float(setbacks.get("side") or 0)
    r = float(setbacks.get("rear") or 0)
    base = {
        0: (s, f, s, r),
        1: (f, s, r, s),
        2: (s, r, s, f),
        3: (r, s, f, s),
    }[q % 4]
    m = WALL_MARGIN
    return (base[0] + m, base[1] + m, base[2] + m, base[3] + m)


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


_MIN_SIDE = 2.4  # narrowest acceptable room dimension (m)


def _pack_block(
    rooms: list[dict], x: float, y: float, w: float, h: float, depth: int = 0
) -> list[dict]:
    """Pack rooms into a rect, splitting into rows/columns when a single
    strip would leave the smallest room narrower than _MIN_SIDE."""
    if not rooms or w <= 0 or h <= 0:
        return []
    if depth < 3 and len(rooms) >= 2:
        horiz = w >= h
        span, cross = (w, h) if horiz else (h, w)
        areas = [max(1, r.get("min_area", 9)) for r in rooms]
        narrowest = span * min(areas) / sum(areas)
        if narrowest < _MIN_SIDE and cross >= 2 * _MIN_SIDE:
            groups: list[list[dict]] = [[], []]
            acc = [0.0, 0.0]
            for room in sorted(rooms, key=lambda r: -r.get("min_area", 9)):
                k = 0 if acc[0] <= acc[1] else 1
                groups[k].append(room)
                acc[k] += room.get("min_area", 9)
            half = cross / 2
            if horiz:
                return _pack_block(groups[0], x, y, w, half, depth + 1) + _pack_block(
                    groups[1], x, y + half, w, h - half, depth + 1
                )
            return _pack_block(groups[0], x, y, half, h, depth + 1) + _pack_block(
                groups[1], x + half, y, w - half, h, depth + 1
            )
    return _pack_strip(rooms, x, y, w, h)


def _layout_rooms(
    rooms: list[dict],
    width: float,
    depth: float,
    seed: int,
    margins: tuple[float, float, float, float] | None = None,
) -> tuple[list[dict], dict]:
    """Partition the usable plot into room rectangles.

    Public zone gets a strip at the entrance edge (y=0); the remaining depth is
    split horizontally between a private block and a service column.
    `margins` is (left, bottom, right, top) — setbacks + wall margin.
    """
    ml, mb, mr, mt = margins or (WALL_MARGIN,) * 4
    x0, y0 = ml, mb
    w, d = max(1.0, width - ml - mr), max(1.0, depth - mb - mt)

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
        placed += _pack_block(public, x0, y0, w, pub_h)
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
            placed += _pack_block(service, x0 + w - svc_w, rest_y, svc_w, rest_h)
            placed += _pack_block(private, x0, rest_y, w - svc_w, rest_h)
        else:
            placed += _pack_block(rest_rooms, x0, rest_y, w, rest_h)

    return placed, {"width": width, "depth": depth}


def _rects_adjacent(a: tuple, b: tuple, tol: float = 0.01) -> tuple | None:
    """Return the shared-edge door spec if two rects share a boundary segment.

    `tol` is the max distance between the touching edges — repairs can shift
    rooms slightly off their original shared wall, so a looser tolerance
    keeps doors near where walls used to be.
    """
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    candidates_v = []
    if abs(ax1 - bx0) < tol:
        candidates_v.append((ax1, ay0, ay1, by0, by1))
    if abs(bx1 - ax0) < tol:
        candidates_v.append((bx1, by0, by1, ay0, ay1))
    for e, lo1, hi1, lo2, hi2 in candidates_v:
        lo, hi = max(lo1, lo2), min(hi1, hi2)
        if hi - lo > 0.8:
            return (round(e, 2), round((lo + hi) / 2, 2), "v")

    candidates_h = []
    if abs(ay1 - by0) < tol:
        candidates_h.append((ay1, ax0, ax1, bx0, bx1))
    if abs(by1 - ay0) < tol:
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
    edge_tol: float = 0.01,
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
            spec = _rects_adjacent(rects[i], rects[j], edge_tol)
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
                    if (abs(ox0 - e) < edge_tol or abs(ox1 - e) < edge_tol) and oy0 < mid < oy1:
                        interior = True
                        break
                else:
                    if (abs(oy0 - e) < edge_tol or abs(oy1 - e) < edge_tol) and ox0 < mid < ox1:
                        interior = True
                        break
            if not interior:
                wx, wy = (e, mid) if orientation == "v" else (mid, e)
                windows.append(
                    {"x": round(wx, 2), "y": round(wy, 2), "orientation": orientation, "floor": floor}
                )

    return doors, windows


def _ensure_connectivity(placed: list[dict], doors: list[dict], edge_tol: float = 0.01) -> None:
    """Guarantee every room can reach an entrance-side room by adding doors.

    BFS over placed-adjacency pairs that already have doors. Unreachable rooms
    get a door to any placed-adjacent non-denied neighbour, falling back to any
    neighbour when no clean option exists.
    """
    rects = [r["_rect"] for r in placed]
    pairs = [
        (i, j, _rects_adjacent(rects[i], rects[j], edge_tol))
        for i in range(len(rects))
        for j in range(i + 1, len(rects))
        if placed[i].get("floor", 1) == placed[j].get("floor", 1)
    ]
    pairs = [(i, j, s) for i, j, s in pairs if s]

    def door_exists(i: int, j: int) -> bool:
        spec = _rects_adjacent(rects[i], rects[j], edge_tol)
        return spec is not None and any(
            d["x"] == spec[0] and d["y"] == spec[1] for d in doors
        )

    # Connectivity is checked per floor — there is no stair geometry, so an
    # upper-floor room can only reach a landing-type room on its own floor.
    LANDING_TYPES = ("entrance", "living", "hallway", "corridor", "stair")
    floors = sorted({r.get("floor", 1) for r in placed})
    for floor in floors:
        floor_idxs = {i for i, r in enumerate(placed) if r.get("floor", 1) == floor}
        if not floor_idxs:
            continue

        def reach() -> set[int]:
            seeds = {i for i in floor_idxs if placed[i].get("type") in LANDING_TYPES}
            if not seeds:
                seeds = {min(floor_idxs)}
            seen = set(seeds)
            frontier = list(seeds)
            while frontier:
                cur = frontier.pop()
                for i, j, _ in pairs:
                    if i not in floor_idxs:
                        continue
                    other = j if i == cur else i if j == cur else None
                    if other is not None and other not in seen and door_exists(i, j):
                        seen.add(other)
                        frontier.append(other)
            return seen

        for _ in range(len(floor_idxs)):
            reached = reach()
            missing = sorted(floor_idxs - reached)
            if not missing:
                break
            i = missing[0]
            neighbours = [
                (i, j if a == i else a, s)
                for a, j, s in pairs
                if a == i or j == i
            ]
            # Prefer doors into the reached component, then non-denied pairs.
            neighbours.sort(
                key=lambda t: (
                    t[1] not in reached,
                    _door_denied(placed[i].get("type", ""), placed[t[1]].get("type", "")),
                )
            )
            added = False
            for _, _, spec in neighbours:
                doors.append(
                    {"x": spec[0], "y": spec[1], "orientation": spec[2], "floor": floor}
                )
                added = True
                break
            if not added:
                break


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
    margins = _layout_margins(quarter_turns, site.get("setbacks") or {})

    candidates = []
    base_score = 0.75
    for i in range(n_candidates):
        placed: list[dict] = []
        for f, f_rooms in enumerate(floor_rooms, start=1):
            f_placed, plot = _layout_rooms(
                [dict(r) for r in f_rooms],
                layout_w,
                layout_d,
                seed=42 + i * 997 + f * 131,
                margins=margins,
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
