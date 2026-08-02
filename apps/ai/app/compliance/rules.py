from __future__ import annotations
from typing import List, Dict, Any

# Simplified Nigerian Building Code (NBC) subset for residential buildings.
# Values are indicative and should be replaced with official code extracts.

NIGERIA_NBC: Dict[str, Any] = {
    "version": "2025.1",
    "jurisdiction": "Nigeria",
    "setbacks": {"front": 6.0, "side": 3.0, "rear": 3.0, "unit": "m"},
    "min_room_dimensions": {
        "living": {"area": 12.0, "width": 3.0, "depth": 3.0, "unit": "m"},
        "bedroom": {"area": 9.0, "width": 2.7, "depth": 2.7, "unit": "m"},
        "kitchen": {"area": 6.0, "width": 2.4, "depth": 2.4, "unit": "m"},
        "bathroom": {"area": 2.4, "width": 1.2, "depth": 1.2, "unit": "m"},
        "corridor": {"width": 1.1, "unit": "m"},
    },
    "ventilation": {
        "window_area_to_floor_area_ratio": 0.10,
        "unit": "ratio",
    },
}


def get_nigeria_rules() -> List[Dict[str, Any]]:
    """Flatten ruleset into a list of rule records for the rule engine."""
    rules: List[Dict[str, Any]] = []
    setback = NIGERIA_NBC["setbacks"]
    rules.append({
        "id": "nbc-setback-front",
        "ruleType": "setback",
        "jurisdiction": "Nigeria",
        "parameters": {"edge": "front", "distance": setback["front"], "unit": setback["unit"]},
    })
    rules.append({
        "id": "nbc-setback-side",
        "ruleType": "setback",
        "jurisdiction": "Nigeria",
        "parameters": {"edge": "side", "distance": setback["side"], "unit": setback["unit"]},
    })
    rules.append({
        "id": "nbc-setback-rear",
        "ruleType": "setback",
        "jurisdiction": "Nigeria",
        "parameters": {"edge": "rear", "distance": setback["rear"], "unit": setback["unit"]},
    })
    for room_type, dims in NIGERIA_NBC["min_room_dimensions"].items():
        rules.append({
            "id": f"nbc-min-{room_type}",
            "ruleType": "min_room_size",
            "jurisdiction": "Nigeria",
            "parameters": {"roomType": room_type, **dims},
        })
    rules.append({
        "id": "nbc-circulation",
        "ruleType": "circulation",
        "jurisdiction": "Nigeria",
        "parameters": {"description": "Every room must be reachable from an entrance"},
    })
    rules.append({
        "id": "nbc-overlap",
        "ruleType": "overlap",
        "jurisdiction": "Nigeria",
        "parameters": {"description": "Rooms must not overlap"},
    })
    rules.append({
        "id": "nbc-ventilation",
        "ruleType": "ventilation",
        "jurisdiction": "Nigeria",
        "parameters": NIGERIA_NBC["ventilation"],
    })
    return rules


RULESETS: Dict[str, Dict[str, Any]] = {
    "Nigeria": NIGERIA_NBC,
}
