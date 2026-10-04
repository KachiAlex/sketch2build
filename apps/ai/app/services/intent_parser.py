import re
from typing import Any

# Typical floor-area fraction per room type, used for min_area estimation.
ROOM_AREA_FRACTION = {
    "living": 0.25,
    "kitchen": 0.12,
    "dining": 0.12,
    "bedroom": 0.15,
    "bathroom": 0.06,
    "office": 0.10,
    "garage": 0.15,
    "storage": 0.05,
    "hallway": 0.06,
    "entrance": 0.05,
    "balcony": 0.08,
    "utility": 0.05,
}

# Keyword phrases (lowercase) mapped to canonical room types. Longer phrases
# are matched first so "master bedroom" and "dining room" win over fragments.
ROOM_KEYWORDS = [
    ("master bedroom", "bedroom"),
    ("guest bedroom", "bedroom"),
    ("dining room", "dining"),
    ("living room", "living"),
    ("family room", "living"),
    ("meeting room", "office"),
    ("conference room", "office"),
    ("reception", "entrance"),
    ("bedroom", "bedroom"),
    ("living", "living"),
    ("lounge", "living"),
    ("kitchen", "kitchen"),
    ("kitchenette", "kitchen"),
    ("dining", "dining"),
    ("bathroom", "bathroom"),
    ("en-suite", "bathroom"),
    ("ensuite", "bathroom"),
    ("restroom", "bathroom"),
    ("toilet", "bathroom"),
    ("wc", "bathroom"),
    ("office", "office"),
    ("study", "office"),
    ("workspace", "office"),
    ("garage", "garage"),
    ("storage", "storage"),
    ("store", "storage"),
    ("balcony", "balcony"),
    ("hallway", "hallway"),
    ("corridor", "hallway"),
    ("entrance", "entrance"),
    ("foyer", "entrance"),
    ("utility", "utility"),
    ("laundry", "utility"),
]

DEFAULT_ADJACENCY = {
    "living": ["entrance", "kitchen", "dining"],
    "kitchen": ["living", "dining"],
    "dining": ["kitchen", "living"],
    "bedroom": ["hallway", "living", "bathroom"],
    "bathroom": ["bedroom", "hallway"],
    "office": ["entrance", "hallway"],
    "garage": ["entrance", "utility"],
    "storage": ["hallway", "utility"],
    "hallway": ["entrance", "living"],
    "entrance": ["living", "hallway"],
    "balcony": ["living", "bedroom"],
    "utility": ["kitchen", "garage"],
}


def _count_phrase(prompt: str, unit_words: list[str]) -> int:
    """Return the numeric count for phrases like '3 bedrooms' / '2-bathroom'.

    Falls back to counting keyword occurrences; returns 0 if not mentioned.
    """
    for word in unit_words:
        m = re.search(rf"(\d+)\s*[-–]?\s*{word}s?\b", prompt)
        if m:
            return int(m.group(1))
    return sum(len(re.findall(rf"\b{w}s?\b", prompt)) for w in unit_words)


def _extract_rooms(prompt: str, plot_area: float) -> list[dict[str, Any]]:
    """Best-effort room program extracted from a free-text brief."""
    found: list[dict[str, Any]] = []
    seen: dict[str, int] = {}

    # Bedroom and bathroom counts often carry explicit numbers in briefs.
    counts = {
        "bedroom": _count_phrase(prompt, ["bedroom", "bed"]),
        "bathroom": _count_phrase(prompt, ["bathroom", "toilet", "restroom", "wc"]),
    }

    for keyword, room_type in ROOM_KEYWORDS:
        if keyword not in prompt:
            continue
        if room_type in counts and counts[room_type] > 0:
            continue  # handled by explicit count below
        if seen.get(room_type, 0) == 0:
            seen[room_type] = 1
            fraction = ROOM_AREA_FRACTION.get(room_type, 0.1)
            found.append(
                {
                    "type": room_type,
                    "min_area": round(plot_area * fraction, 2),
                    "adjacency": DEFAULT_ADJACENCY.get(room_type, []),
                }
            )

    for room_type, count in counts.items():
        for _ in range(min(count, 8)):
            fraction = ROOM_AREA_FRACTION.get(room_type, 0.1)
            found.append(
                {
                    "type": room_type,
                    "min_area": round(plot_area * fraction, 2),
                    "adjacency": DEFAULT_ADJACENCY.get(room_type, []),
                }
            )

    return found


def _default_rooms(room_count: int, plot_area: float) -> list[dict[str, Any]]:
    sequence = ["living", "kitchen", "bedroom", "bathroom"]
    rooms = []
    for room_type in sequence[: max(1, room_count)]:
        rooms.append(
            {
                "type": room_type,
                "min_area": round(plot_area * ROOM_AREA_FRACTION[room_type], 2),
                "adjacency": DEFAULT_ADJACENCY.get(room_type, []),
            }
        )
    return rooms


def parse_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Map a design brief (frontend payload or flat fields) to a structured program.

    Accepts the nested `site` object the web app sends ({width, depth, unit})
    as well as legacy flat keys (plot_width, plot_depth, unit). Room types are
    extracted from the free-text prompt when present; otherwise `room_count`
    drives a default sequence. A production version will use an LLM for the
    extraction step.
    """
    site = brief.get("site") or {}
    unit = site.get("unit") or brief.get("unit", "m")
    width = site.get("width") or brief.get("plot_width") or brief.get("plotWidth") or 10.0
    depth = site.get("depth") or brief.get("plot_depth") or brief.get("plotDepth") or 10.0

    try:
        plot_area = max(1.0, float(width) * float(depth))
    except (TypeError, ValueError):
        plot_area = 100.0

    prompt = (brief.get("prompt") or "").lower()
    rooms = _extract_rooms(prompt, plot_area) if prompt else []
    if not rooms:
        room_count = brief.get("room_count") or 3
        rooms = _default_rooms(int(room_count), plot_area)

    return {
        "site": {"width": width, "depth": depth, "unit": unit},
        "orientation": brief.get("orientation"),
        "style": brief.get("style", "modern"),
        "rooms": rooms,
        "floors": brief.get("floors") or 1,
        "generate_alternatives": brief.get("generate_alternatives") or 3,
        "compliance_standard": brief.get("compliance_standard"),
        "regional_profile": brief.get("regional_profile"),
        "constraints": brief.get("constraints", []),
    }
