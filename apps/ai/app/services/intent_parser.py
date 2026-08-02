from typing import Any


def parse_brief(brief: dict[str, Any]) -> dict[str, Any]:
    """Placeholder intent parser that maps a design brief to a structured program.

    A production version will use an LLM to extract rooms, areas, adjacencies,
    orientation and style from the free-text prompt.
    """
    unit = brief.get("unit", "m")
    width = brief.get("plot_width", 10.0)
    depth = brief.get("plot_depth", 10.0)
    room_count = brief.get("room_count", 3)

    rooms = []
    if room_count >= 1:
        rooms.append({"type": "living", "min_area": width * depth * 0.25, "adjacency": []})
    if room_count >= 2:
        rooms.append({"type": "kitchen", "min_area": width * depth * 0.12, "adjacency": ["living"]})
    if room_count >= 3:
        rooms.append({"type": "bedroom", "min_area": width * depth * 0.18, "adjacency": ["living"]})
    if room_count >= 4:
        rooms.append({"type": "bathroom", "min_area": width * depth * 0.08, "adjacency": ["bedroom"]})

    return {
        "site": {"width": width, "depth": depth, "unit": unit},
        "orientation": brief.get("orientation"),
        "style": brief.get("style", "modern"),
        "rooms": rooms,
        "constraints": brief.get("constraints", []),
    }
