from __future__ import annotations
from typing import Any, Dict, List
from .geometry import (
    Polygon,
    Rect,
    polygon_area,
    detect_overlaps,
    check_setback,
    build_room_graph,
    all_rooms_reachable,
)
from .rules import RULESETS, get_nigeria_rules


def _room_boundary(room: Dict[str, Any]) -> Polygon:
    return room.get("boundaryGeometry", [])


def _find_entrance_index(rooms: List[Dict[str, Any]]) -> int:
    for idx, room in enumerate(rooms):
        if room.get("type") in ("entrance", "corridor", "living"):
            return idx
    return 0


def validate_layout(layout: Dict[str, Any], jurisdiction: str = "Nigeria") -> Dict[str, Any]:
    """Validate a candidate layout against the active ruleset.

    `layout` shape:
    {
      "site": [[x,y], ...],
      "rooms": [
        {"type": "bedroom", "area": 10, "boundaryGeometry": [[...], ...]},
        ...
      ]
    }
    """
    ruleset = RULESETS.get(jurisdiction)
    if not ruleset:
        return {
            "status": "failed",
            "error": f"Unknown jurisdiction: {jurisdiction}",
            "violations": [],
        }

    violations: List[Dict[str, Any]] = []
    rooms = layout.get("rooms", [])
    site = layout.get("site", [])

    # Geometry checks
    overlaps = detect_overlaps([_room_boundary(r) for r in rooms])
    for i, j in overlaps:
        violations.append(
            {
                "ruleId": "nbc-overlap",
                "ruleType": "overlap",
                "message": f"Rooms {i} and {j} overlap",
                "location": f"rooms[{i}], rooms[{j}]",
                "severity": "error",
            }
        )

    # Circulation
    if rooms:
        graph = build_room_graph([_room_boundary(r) for r in rooms])
        entrance = _find_entrance_index(rooms)
        if not all_rooms_reachable(graph, entrance):
            violations.append(
                {
                    "ruleId": "nbc-circulation",
                    "ruleType": "circulation",
                    "message": "Not all rooms are reachable from the entrance/living area",
                    "location": "room graph",
                    "severity": "error",
                }
            )

    # Setback: use building outline (union bounding box of rooms)
    if site and rooms:
        site_rect = Rect.from_polygon(site)
        room_rects = [Rect.from_polygon(_room_boundary(r)) for r in rooms]
        building_rect = Rect(
            min(r.x_min for r in room_rects),
            min(r.y_min for r in room_rects),
            max(r.x_max for r in room_rects),
            max(r.y_max for r in room_rects),
        )
        setback = ruleset["setbacks"]
        for edge, distance in [("front", setback["front"]), ("side", setback["side"]), ("rear", setback["rear"])]:
            if not check_setback(site, [[building_rect.x_min, building_rect.y_min], [building_rect.x_max, building_rect.y_min], [building_rect.x_max, building_rect.y_max], [building_rect.x_min, building_rect.y_max]], distance):
                # Produce one violation per violated edge for clarity
                if building_rect.x_min < site_rect.x_min + distance:
                    violations.append(_setback_violation(edge, "left", distance))
                if building_rect.x_max > site_rect.x_max - distance:
                    violations.append(_setback_violation(edge, "right", distance))
                if building_rect.y_min < site_rect.y_min + distance:
                    violations.append(_setback_violation(edge, "bottom", distance))
                if building_rect.y_max > site_rect.y_max - distance:
                    violations.append(_setback_violation(edge, "top", distance))

    # Minimum room dimensions
    min_dims = ruleset["min_room_dimensions"]
    for idx, room in enumerate(rooms):
        room_type = room.get("type", "room")
        boundary = _room_boundary(room)
        actual_area = polygon_area(boundary)
        declared_area = room.get("area", actual_area)
        rect = Rect.from_polygon(boundary)

        spec = min_dims.get(room_type)
        if not spec:
            continue

        if "area" in spec and actual_area < spec["area"]:
            violations.append(
                {
                    "ruleId": f"nbc-min-{room_type}",
                    "ruleType": "min_room_size",
                    "message": f"{room_type.capitalize()} room area {actual_area:.2f} m² is below minimum {spec['area']} m²",
                    "location": f"rooms[{idx}]",
                    "severity": "error",
                }
            )
        if "width" in spec and rect.width() < spec["width"]:
            violations.append(
                {
                    "ruleId": f"nbc-min-{room_type}",
                    "ruleType": "min_room_size",
                    "message": f"{room_type.capitalize()} room width {rect.width():.2f} m is below minimum {spec['width']} m",
                    "location": f"rooms[{idx}]",
                    "severity": "error",
                }
            )
        if "depth" in spec and rect.depth() < spec["depth"]:
            violations.append(
                {
                    "ruleId": f"nbc-min-{room_type}",
                    "ruleType": "min_room_size",
                    "message": f"{room_type.capitalize()} room depth {rect.depth():.2f} m is below minimum {spec['depth']} m",
                    "location": f"rooms[{idx}]",
                    "severity": "error",
                }
            )

        # Ventilation heuristic: assume window length = half perimeter, area = wall height * length
        # Simplified: flag if room area is tiny relative to perimeter
        if room_type not in ("corridor", "bathroom"):
            pass  # Full window-area calculation requires wall height; stub for now.

    return {
        "status": "completed",
        "jurisdiction": jurisdiction,
        "rulesetVersion": ruleset["version"],
        "violations": violations,
        "passed": len(violations) == 0,
    }


def _setback_violation(edge: str, side: str, distance: float) -> Dict[str, Any]:
    return {
        "ruleId": f"nbc-setback-{edge}",
        "ruleType": "setback",
        "message": f"Building violates {edge} setback ({distance} m) on {side} side",
        "location": f"site {edge}/{side}",
        "severity": "error",
    }


def list_rules(jurisdiction: str = "Nigeria") -> List[Dict[str, Any]]:
    if jurisdiction == "Nigeria":
        return get_nigeria_rules()
    return []
