import random
from typing import Any


def generate_candidates(program: dict[str, Any]) -> list[dict[str, Any]]:
    """Placeholder geometry generator that returns ranked candidate layouts.

    In production this will be a rule-based packing and snapping engine that
    fits rooms into the site boundary while satisfying adjacency and code rules.
    """
    site = program.get("site", {})
    width = site.get("width", 10.0)
    depth = site.get("depth", 10.0)
    unit = site.get("unit", "m")
    rooms = program.get("rooms", [])

    candidates = []
    base_score = 0.75
    for i in range(3):
        score = min(0.99, base_score + random.uniform(-0.1, 0.1))
        offset = i * 0.3
        candidate_rooms = []
        for idx, room in enumerate(rooms):
            room_width = max(1.0, (width * 0.4) - offset - idx * 0.2)
            room_depth = max(1.0, (room.get("min_area", 9.0) / room_width))
            x = (idx % 2) * (width * 0.5)
            y = (idx // 2) * (depth * 0.5)
            candidate_rooms.append(
                {
                    "type": room.get("type"),
                    "label": room.get("type", "Room").capitalize(),
                    "area": round(room_width * room_depth, 2),
                    "boundaryGeometry": [
                        [round(x, 2), round(y, 2)],
                        [round(x + room_width, 2), round(y, 2)],
                        [round(x + room_width, 2), round(y + room_depth, 2)],
                        [round(x, 2), round(y + room_depth, 2)],
                    ],
                }
            )
        candidates.append(
            {
                "rank": i + 1,
                "score": round(score, 2),
                "unit": unit,
                "rationale": {
                    "areaEfficiency": round(random.uniform(0.7, 0.95), 2),
                    "adjacencySatisfaction": round(random.uniform(0.6, 0.95), 2),
                    "lightAndVentilation": round(random.uniform(0.5, 0.9), 2),
                },
                "rooms": candidate_rooms,
            }
        )

    # Ensure candidates are sorted by descending score
    candidates.sort(key=lambda c: c["score"], reverse=True)
    for i, c in enumerate(candidates):
        c["rank"] = i + 1

    return candidates
