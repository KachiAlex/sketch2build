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
        if site:
            sr = Rect.from_polygon(site)
            sb = ruleset.get("setbacks", {})
            inset = (
                sr.x_min + float(sb.get("side", 0) or 0),
                sr.y_min + float(sb.get("front", 0) or 0),
                sr.x_max - float(sb.get("side", 0) or 0),
                sr.y_max - float(sb.get("rear", 0) or 0),
            )
            rects = [_rect_of(r) for r in rooms]
            bx0 = min(r[0] for r in rects)
            by0 = min(r[1] for r in rects)
            bx1 = max(r[2] for r in rects)
            by1 = max(r[3] for r in rects)

            dx = max(inset[0] - bx0, 0) or min(inset[2] - bx1, 0)
            dy = max(inset[1] - by0, 0) or min(inset[3] - by1, 0)
            if dx or dy:
                for room in rooms:
                    x0, y0, x1, y1 = _rect_of(room)
                    _set_rect(room, x0 + dx, y0 + dy, x1 + dx, y1 + dy)
                log.append(f"Moved building {dx:.2f},{dy:.2f} inside setback box")
                changed = True

            # Scale down if still too large (coverage or oversized rooms).
            rects = [_rect_of(r) for r in rooms]
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

        # --- 2. Min room dimensions: grow undersized rooms ---
        min_dims = ruleset.get("min_room_dimensions", {})
        for room in rooms:
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
                _set_rect(room, cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2)
                log.append(f"Enlarged {room.get('type')} by {grow:.2f}x to meet minimum size")
                changed = True

        # --- 3. Overlap resolution: push later rooms apart ---
        # Cross-floor pairs overlap legitimately — only separate same-floor rooms.
        rects = [_rect_of(r) for r in rooms]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                if rooms[i].get("floor", 1) != rooms[j].get("floor", 1):
                    continue
                a, b = rects[i], rects[j]
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox > 0.05 and oy > 0.05:
                    room = rooms[j]
                    x0, y0, x1, y1 = _rect_of(room)
                    if ox <= oy:
                        shift = ox if (b[0] >= a[0]) else -ox
                        _set_rect(room, x0 + shift, y0, x1 + shift, y1)
                    else:
                        shift = oy if (b[1] >= a[1]) else -oy
                        _set_rect(room, x0, y0 + shift, x1, y1 + shift)
                    log.append(f"Separated overlapping rooms {i} and {j}")
                    changed = True
                    rects = [_rect_of(r) for r in rooms]
                    break
            if changed:
                break

        if not changed:
            break

    return layout, log
