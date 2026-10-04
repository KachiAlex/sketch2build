"""Heuristic compliance repair: nudge room rectangles to resolve violations.

Repairs applied (each logged):
  1. Setback      — translate the whole building inside the setback box;
                    if it doesn't fit, scale all rooms down about the
                    setback box's origin.
  2. Min room dim — scale undersized rooms up toward the building centre.
  3. Overlap      — push overlapping rooms apart along the smaller axis.
  4. Coverage     — uniform downscale handled by the setback pass.

Repairs are axis-aligned only — rooms stay rectangles. Circulation
violations are not auto-fixable.
"""
from __future__ import annotations
from typing import Any, Dict, List, Tuple

from .geometry import Rect, polygon_area

MAX_PASSES = 3


def _rect_of(room: Dict[str, Any]) -> Tuple[float, float, float, float]:
    r = Rect.from_polygon(room["boundaryGeometry"])
    return r.x_min, r.y_min, r.x_max, r.y_max


def _set_rect(room: Dict[str, Any], x0: float, y0: float, x1: float, y1: float) -> None:
    room["boundaryGeometry"] = [
        [round(x0, 2), round(y0, 2)],
        [round(x1, 2), round(y0, 2)],
        [round(x1, 2), round(y1, 2)],
        [round(x0, 2), round(y1, 2)],
    ]
    room["area"] = round(abs(x1 - x0) * abs(y1 - y0), 2)


def _overlaps_other(rooms: List[Dict[str, Any]], idx: int, rect: Tuple[float, float, float, float]) -> bool:
    """True if `rect` (as rooms[idx]) overlaps any other same-floor room."""
    floor = rooms[idx].get("floor", 1)
    x0, y0, x1, y1 = rect
    for k, other in enumerate(rooms):
        if k == idx or other.get("floor", 1) != floor:
            continue
        ox0, oy0, ox1, oy1 = _rect_of(other)
        if min(x1, ox1) - max(x0, ox0) > 0.05 and min(y1, oy1) - max(y0, oy0) > 0.05:
            return True
    return False


def repair_layout(layout: Dict[str, Any], ruleset: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Return (repaired_layout, repair_log). Mutates a copy of the layout."""
    import copy

    layout = copy.deepcopy(layout)
    rooms = layout.get("rooms", [])
    site = layout.get("site", [])
    log: List[str] = []
    if not rooms:
        return layout, log

    for _ in range(MAX_PASSES):
        changed = False

        # --- 1. Setback / coverage: fit building inside the allowed box ---
        # Ground-floor rooms define the footprint; upper floors move with them.
        ground = [r for r in rooms if r.get("floor", 1) == 1] or rooms
        if site:
            sr = Rect.from_polygon(site)
            sb = ruleset.get("setbacks", {})
            inset = (
                sr.x_min + float(sb.get("side", 0) or 0),
                sr.y_min + float(sb.get("front", 0) or 0),
                sr.x_max - float(sb.get("side", 0) or 0),
                sr.y_max - float(sb.get("rear", 0) or 0),
            )
            rects = [_rect_of(r) for r in ground]
            bx0 = min(r[0] for r in rects)
            by0 = min(r[1] for r in rects)
            bx1 = max(r[2] for r in rects)
            by1 = max(r[3] for r in rects)

            dx = max(inset[0] - bx0, 0) or min(inset[2] - bx1, 0)
            dy = max(inset[1] - by0, 0) or min(inset[3] - by1, 0)
            if dx or dy:
                # Translate the whole building (all floors) so it stays stacked.
                for room in rooms:
                    x0, y0, x1, y1 = _rect_of(room)
                    _set_rect(room, x0 + dx, y0 + dy, x1 + dx, y1 + dy)
                log.append(f"Moved building {dx:.2f},{dy:.2f} inside setback box")
                changed = True

            # Scale the ground floor down if the footprint exceeds the setback
            # box or the plot-coverage cap; upper floors follow the same
            # transform so stacking is preserved.
            rects = [_rect_of(r) for r in ground]
            bx0 = min(r[0] for r in rects)
            by0 = min(r[1] for r in rects)
            bx1 = max(r[2] for r in rects)
            by1 = max(r[3] for r in rects)
            bw, bh = bx1 - bx0, by1 - by0
            aw, ah = inset[2] - inset[0], inset[3] - inset[1]
            coverage = ruleset.get("plot_coverage")
            scale = min(1.0, aw / bw if bw else 1.0, ah / bh if bh else 1.0)
            if coverage and polygon_area(site) > 0:
                scale = min(scale, coverage * polygon_area(site) / max(bw * bh, 0.01))
            if scale < 0.999:
                for room in rooms:
                    x0, y0, x1, y1 = _rect_of(room)
                    _set_rect(
                        room,
                        inset[0] + (x0 - bx0) * scale,
                        inset[1] + (y0 - by0) * scale,
                        inset[0] + (x1 - bx0) * scale,
                        inset[1] + (y1 - by0) * scale,
                    )
                log.append(f"Scaled building footprint by {scale:.2f} to fit setbacks/coverage")
                changed = True

        # --- 2. Min room dimensions: grow undersized rooms into free space ---
        # Growth that would overlap a same-floor neighbour is reverted — the
        # violation is left for the validator to report honestly rather than
        # trading a size violation for an overlap violation.
        min_dims = ruleset.get("min_room_dimensions", {})
        for idx, room in enumerate(rooms):
            spec = min_dims.get(room.get("type", ""))
            if not spec:
                continue
            x0, y0, x1, y1 = _rect_of(room)
            w, h = x1 - x0, y1 - y0
            need_w = float(spec.get("width") or 0)
            need_h = float(spec.get("depth") or 0)
            need_a = float(spec.get("area") or 0)
            grow = 1.0
            if need_a and w * h < need_a:
                grow = max(grow, (need_a / max(w * h, 0.01)) ** 0.5)
            if need_w and w < need_w:
                grow = max(grow, need_w / w)
            if need_h and h < need_h:
                grow = max(grow, need_h / h)
            if grow > 1.01:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                nw, nh = w * grow, h * grow
                grown = (cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2)
                if not _overlaps_other(rooms, idx, grown):
                    _set_rect(room, *grown)
                    log.append(f"Enlarged {room.get('type')} by {grow:.2f}x to meet minimum size")
                    changed = True

        # --- 3. Overlap resolution: push rooms apart without cascading ---
        # Cross-floor pairs overlap legitimately — only same-floor pairs count.
        # A push that would create a new overlap is tried in the opposite
        # direction, then reverted if neither side is free.
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                if rooms[i].get("floor", 1) != rooms[j].get("floor", 1):
                    continue
                a, b = _rect_of(rooms[i]), _rect_of(rooms[j])
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox <= 0.05 or oy <= 0.05:
                    continue
                # Push the overlapping rooms apart — prefer the later room
                # along the smaller overlap axis, then fall back to the other
                # room and the other axis. A push that collides with a third
                # room (or doesn't fully separate the pair) is skipped.
                resolved = False
                for mover, other, along_x in (
                    (j, i, ox <= oy),
                    (i, j, ox <= oy),
                    (j, i, ox > oy),
                    (i, j, ox > oy),
                ):
                    mx0, my0, mx1, my1 = _rect_of(rooms[mover])
                    o = _rect_of(rooms[other])
                    if along_x:
                        amt = ox if mx0 >= o[0] else -ox
                        cand = (mx0 + amt, my0, mx1 + amt, my1)
                    else:
                        amt = oy if my0 >= o[1] else -oy
                        cand = (mx0, my0 + amt, mx1, my1 + amt)
                    if not _overlaps_other(rooms, mover, cand):
                        _set_rect(rooms[mover], *cand)
                        log.append(f"Separated overlapping rooms {i} and {j}")
                        changed = True
                        break

        if not changed:
            break

    return layout, log
