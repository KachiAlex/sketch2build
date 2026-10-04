from __future__ import annotations
import copy
from typing import Any, Dict, List, Optional
from .geometry import (
    Polygon,
    Rect,
    polygon_area,
    detect_overlaps,
    check_setback,
    build_room_graph,
    all_rooms_reachable,
)
from .rules import RULESETS, get_nigeria_rules, canonical_jurisdiction


def _room_boundary(room: Dict[str, Any]) -> Polygon:
    return room.get("boundaryGeometry", [])


def _find_entrance_index(rooms: List[Dict[str, Any]]) -> int:
    for idx, room in enumerate(rooms):
        if room.get("type") in ("entrance", "corridor", "living"):
            return idx
    return 0


def build_ruleset(jurisdiction: str, rules: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Resolve a ruleset: canonical base ruleset merged with DB rule records.

    `rules` records use the DB ComplianceRule shape:
        {"ruleType": "setback", "parameters": {"edge": "front", "distance": 6}}
    Recognised ruleTypes: setback, min_room_size | room_size, corridor_width,
    ventilation, plot_coverage. Unknown types are ignored.
    """
    key = canonical_jurisdiction(jurisdiction)
    base = RULESETS.get(key) or RULESETS.get("Nigeria")
    if base is None:
        return None
    ruleset = copy.deepcopy(base)
    ruleset["jurisdiction"] = jurisdiction

    for rule in rules or []:
        rtype = rule.get("ruleType", "")
        p = rule.get("parameters") or {}
        try:
            if rtype == "setback" and p.get("edge") and p.get("distance") is not None:
                ruleset["setbacks"][str(p["edge"])] = float(p["distance"])
            elif rtype == "setback":
                # Legacy flat shape: {front, rear, side | left, right}
                for edge, value in (
                    ("front", p.get("front")),
                    ("rear", p.get("rear")),
                    ("side", p.get("side", p.get("left"))),
                ):
                    if value is not None:
                        ruleset["setbacks"][edge] = float(value)
            elif rtype in ("min_room_size", "room_size") and p.get("roomType"):
                rt = str(p["roomType"])
                spec = ruleset["min_room_dimensions"].setdefault(rt, {"unit": "m"})
                for k in ("area", "width", "depth"):
                    if p.get(k) is not None:
                        spec[k] = float(p[k])
            elif rtype == "corridor_width" and p.get("width") is not None:
                spec = ruleset["min_room_dimensions"].setdefault("corridor", {"unit": "m"})
                spec["width"] = float(p["width"])
            elif rtype == "ventilation":
                ratio = p.get("ratio", p.get("window_area_to_floor_area_ratio"))
                if ratio is not None:
                    ruleset["ventilation"]["window_area_to_floor_area_ratio"] = float(ratio)
            elif rtype == "plot_coverage" and (p.get("maxRatio") is not None or p.get("ratio") is not None):
                ruleset["plot_coverage"] = float(p.get("maxRatio", p.get("ratio")))
        except (TypeError, ValueError):
            continue
    return ruleset


def validate_layout(
    layout: Dict[str, Any],
    jurisdiction: str = "Nigeria",
    rules: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Validate a candidate layout against the resolved ruleset."""
    ruleset = build_ruleset(jurisdiction, rules)
    if not ruleset:
        return {
            "status": "failed",
            "error": f"Unknown jurisdiction: {jurisdiction}",
            "violations": [],
        }

    violations: List[Dict[str, Any]] = []
    rooms = layout.get("rooms", [])
    site = layout.get("site", [])

    # Geometry checks — per floor: rooms on different storeys overlap
    # legitimately in plan view, so pairs are only compared within a floor.
    floor_nums = sorted({r.get("floor", 1) for r in rooms} or {1})
    for floor in floor_nums:
        idxs = [i for i, r in enumerate(rooms) if r.get("floor", 1) == floor]
        sub_rooms = [rooms[i] for i in idxs]
        boundaries = [_room_boundary(r) for r in sub_rooms]

        overlaps = detect_overlaps(boundaries)
        for a, b in overlaps:
            i, j = idxs[a], idxs[b]
            violations.append(
                {
                    "ruleId": "overlap",
                    "ruleType": "overlap",
                    "message": f"Rooms {i} and {j} overlap on floor {floor}",
                    "location": f"rooms[{i}], rooms[{j}]",
                    "severity": "error",
                }
            )

        # Circulation: every room on this floor reachable from a landing room
        if boundaries:
            graph = build_room_graph(boundaries)
            entrance = _find_entrance_index(sub_rooms)
            if not all_rooms_reachable(graph, entrance):
                violations.append(
                    {
                        "ruleId": "circulation",
                        "ruleType": "circulation",
                        "message": f"Not all rooms on floor {floor} are reachable from the entrance/living area",
                        "location": "room graph",
                        "severity": "error",
                    }
                )

    # Setback + plot coverage against the ground-floor building outline
    ground_rooms = [r for r in rooms if r.get("floor", 1) == 1] or rooms
    if site and ground_rooms:
        site_rect = Rect.from_polygon(site)
        room_rects = [Rect.from_polygon(_room_boundary(r)) for r in ground_rooms]
        building_rect = Rect(
            min(r.x_min for r in room_rects),
            min(r.y_min for r in room_rects),
            max(r.x_max for r in room_rects),
            max(r.y_max for r in room_rects),
        )
        setback = ruleset["setbacks"]
        # Edge semantics: front = entrance edge (bottom, y_min); side = both
        # x edges; rear = top edge (y_max). Each edge uses its own distance.
        edge_checks = [
            ("front", "bottom", building_rect.y_min < site_rect.y_min + float(setback.get("front") or 0)),
            ("rear", "top", building_rect.y_max > site_rect.y_max - float(setback.get("rear") or 0)),
            ("side", "left", building_rect.x_min < site_rect.x_min + float(setback.get("side") or 0)),
            ("side", "right", building_rect.x_max > site_rect.x_max - float(setback.get("side") or 0)),
        ]
        for edge, side, fails in edge_checks:
            distance = float(setback.get(edge) or 0)
            if distance and fails:
                violations.append(_setback_violation(edge, side, distance))

        max_coverage = ruleset.get("plot_coverage")
        site_area = polygon_area(site)
        if max_coverage and site_area > 0:
            building_area = (building_rect.x_max - building_rect.x_min) * (
                building_rect.y_max - building_rect.y_min
            )
            coverage = building_area / site_area
            if coverage > max_coverage:
                violations.append(
                    {
                        "ruleId": "plot-coverage",
                        "ruleType": "plot_coverage",
                        "message": f"Building covers {coverage:.0%} of the plot, above the {max_coverage:.0%} maximum",
                        "location": "site",
                        "severity": "error",
                    }
                )

    # Minimum room dimensions
    min_dims = ruleset["min_room_dimensions"]
    for idx, room in enumerate(rooms):
        room_type = room.get("type", "room")
        boundary = _room_boundary(room)
        actual_area = polygon_area(boundary)
        rect = Rect.from_polygon(boundary)

        spec = min_dims.get(room_type)
        if not spec:
            continue

        if "area" in spec and actual_area < spec["area"]:
            violations.append(
                {
                    "ruleId": f"min-{room_type}",
                    "ruleType": "min_room_size",
                    "message": f"{room_type.capitalize()} room area {actual_area:.2f} m² is below minimum {spec['area']} m²",
                    "location": f"rooms[{idx}]",
                    "severity": "error",
                }
            )
        if "width" in spec and rect.width() < spec["width"]:
            violations.append(
                {
                    "ruleId": f"min-{room_type}",
                    "ruleType": "min_room_size",
                    "message": f"{room_type.capitalize()} room width {rect.width():.2f} m is below minimum {spec['width']} m",
                    "location": f"rooms[{idx}]",
                    "severity": "error",
                }
            )
        if "depth" in spec and rect.depth() < spec["depth"]:
            violations.append(
                {
                    "ruleId": f"min-{room_type}",
                    "ruleType": "min_room_size",
                    "message": f"{room_type.capitalize()} room depth {rect.depth():.2f} m is below minimum {spec['depth']} m",
                    "location": f"rooms[{idx}]",
                    "severity": "error",
                }
            )

    return {
        "status": "completed",
        "jurisdiction": jurisdiction,
        "rulesetVersion": ruleset["version"],
        "violations": violations,
        "passed": len(violations) == 0,
    }


def _setback_violation(edge: str, side: str, distance: float) -> Dict[str, Any]:
    return {
        "ruleId": f"setback-{edge}",
        "ruleType": "setback",
        "message": f"Building violates {edge} setback ({distance} m) on {side} side",
        "location": f"site {edge}/{side}",
        "severity": "error",
    }


def list_rules(jurisdiction: str = "Nigeria") -> List[Dict[str, Any]]:
    if canonical_jurisdiction(jurisdiction) == "Nigeria":
        return get_nigeria_rules()
    return []
