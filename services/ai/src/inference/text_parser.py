"""Text-to-Graph parser for prompt-based design generation.

Converts natural language descriptions into structured room adjacency graphs
using keyword extraction, room type matching, and heuristic adjacency inference.
No external LLM dependency — pure rule-based parsing for fast, reliable inference.
"""

import re
import structlog
from typing import Any

logger = structlog.get_logger()


# Room type keywords and synonyms
ROOM_KEYWORDS: dict[str, list[str]] = {
    "living": ["living", "lounge", "family room", "sitting room", "tv room", "great room"],
    "kitchen": ["kitchen", "cook", "galley", "scullery"],
    "bedroom": ["bedroom", "bed room", "master", "sleeping", "bunk"],
    "bathroom": ["bathroom", "bath", "washroom", "restroom", "toilet", "wc", "ensuite", "en-suite", "powder room"],
    "dining": ["dining", "eat-in", "breakfast nook", "breakfast area"],
    "hallway": ["hallway", "hall", "corridor", "passage", "lobby", "foyer"],
    "entrance": ["entrance", "entry", "vestibule", "mudroom", "mud room", "entryway", "porch"],
    "balcony": ["balcony", "terrace", "patio", "deck", "veranda"],
    "storage": ["storage", "closet", "pantry", "walk-in", "linen", "cupboard"],
    "garage": ["garage", "carport", "parking"],
    "office": ["office", "study", "workspace", "library", "den", "workroom"],
    "utility": ["utility", "laundry", "boiler room", "mechanical", "server room"],
    "prayer": ["prayer", "meditation", "chapel", "musalla"],
    "genkan": ["genkan", "shoe room"],
}

# Quantity keywords
QUANTITY_KEYWORDS: dict[str, int] = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "single": 1, "double": 2, "triple": 3,
}

# Size keywords
SIZE_KEYWORDS: dict[str, str] = {
    "small": "small", "tiny": "small", "compact": "small", "cozy": "small",
    "medium": "medium", "standard": "medium", "average": "medium",
    "large": "large", "spacious": "large", "big": "large", "huge": "large",
    "master": "large", "grand": "large", "expansive": "large",
}

# Style keywords
STYLE_KEYWORDS: dict[str, str] = {
    "modern": "modern", "contemporary": "modern", "minimalist": "modern",
    "traditional": "traditional", "classic": "traditional", "colonial": "traditional",
    "scandinavian": "scandinavian", "nordic": "scandinavian",
    "industrial": "industrial", "loft": "industrial",
    "mediterranean": "mediterranean", "tuscan": "mediterranean",
    "japanese": "japanese", "zen": "japanese",
    "tropical": "tropical", "balinese": "tropical",
    "open plan": "open", "open concept": "open", "open floor": "open",
}

# Adjacency hints
ADJACENCY_HINTS: dict[str, list[str]] = {
    "kitchen": ["dining", "living", "hallway", "pantry"],
    "dining": ["kitchen", "living", "hallway"],
    "living": ["dining", "kitchen", "hallway", "entrance", "balcony"],
    "bedroom": ["bathroom", "hallway", "storage"],
    "bathroom": ["bedroom", "hallway"],
    "entrance": ["hallway", "living", "garage"],
    "garage": ["entrance", "hallway", "utility"],
    "office": ["hallway", "living"],
    "utility": ["garage", "kitchen", "hallway"],
    "storage": ["hallway", "bedroom", "kitchen"],
    "balcony": ["living", "bedroom"],
    "hallway": ["entrance", "living", "kitchen", "bedroom", "bathroom", "office"],
}

# Default room areas (sqm) by size
SIZE_AREAS: dict[str, dict[str, float]] = {
    "small": {"living": 14, "kitchen": 6, "bedroom": 8, "bathroom": 3.5, "dining": 8, "office": 6, "hallway": 3, "entrance": 2, "garage": 16, "utility": 3, "storage": 2, "balcony": 3},
    "medium": {"living": 20, "kitchen": 10, "bedroom": 12, "bathroom": 5, "dining": 12, "office": 10, "hallway": 4, "entrance": 3, "garage": 20, "utility": 5, "storage": 3, "balcony": 5},
    "large": {"living": 30, "kitchen": 15, "bedroom": 18, "bathroom": 7, "dining": 18, "office": 15, "hallway": 6, "entrance": 5, "garage": 25, "utility": 7, "storage": 4, "balcony": 8},
}


class TextToGraphParser:
    """Parses natural language descriptions into structured room graphs."""

    def __init__(self, max_rooms: int = 20):
        self.max_rooms = max_rooms

    def parse(self, description: str, constraints: dict | None = None) -> dict[str, Any]:
        """
        Parse a text description into a room adjacency graph.

        Args:
            description: Natural language description of desired floor plan
            constraints: Optional pre-set constraints (plot size, room types, etc.)

        Returns:
            Dict with room_types, room_sizes, adjacency, dimensions, style, parsed_constraints
        """
        if not description:
            description = ""
        text = description.lower().strip()
        constraints = constraints or {}

        # Extract style
        style = "modern"
        for keyword, style_name in STYLE_KEYWORDS.items():
            if keyword in text:
                style = style_name
                break

        # Extract rooms with quantities
        rooms = self._extract_rooms(text, constraints)

        # Extract plot dimensions
        plot_width, plot_depth = self._extract_plot_dimensions(text, constraints)

        # Extract number of floors
        num_floors = self._extract_num_floors(text, constraints)

        # Build adjacency from hints and explicit mentions
        adjacency = self._infer_adjacency(rooms, text)

        # Extract room sizes
        room_sizes = self._extract_room_sizes(text, rooms)

        logger.info(
            "Text parsed to graph",
            rooms=len(rooms),
            style=style,
            plot=f"{plot_width}x{plot_depth}",
            floors=num_floors,
        )

        return {
            "room_types": rooms,
            "room_sizes": room_sizes,
            "adjacency": adjacency,
            "dimensions": {
                "plot_width": plot_width,
                "plot_depth": plot_depth,
                "num_floors": num_floors,
            },
            "style": style,
            "parsed_constraints": constraints,
        }

    def _extract_rooms(self, text: str, constraints: dict) -> list[str]:
        """Extract room types from text, handling quantities."""
        rooms: list[str] = []

        # If constraints specify room types, use those as base
        constraint_rooms = constraints.get("room_types", [])
        if constraint_rooms:
            rooms.extend(constraint_rooms)

        # Scan text for room keywords with quantity detection
        for room_type, keywords in ROOM_KEYWORDS.items():
            for kw in keywords:
                # Check for quantity prefix: "two bedrooms", "3 bathrooms"
                for qty_kw, qty_val in QUANTITY_KEYWORDS.items():
                    pattern = rf"{qty_kw}\s+{kw}"
                    if re.search(pattern, text):
                        for _ in range(qty_val):
                            if room_type not in rooms or rooms.count(room_type) < qty_val:
                                rooms.append(room_type)
                        break
                else:
                    # No quantity prefix — check for plural or singular
                    if re.search(rf"\b{kw}\b", text):
                        if room_type not in rooms:
                            rooms.append(room_type)

        # Deduplicate but allow multiple bedrooms/bathrooms
        # Keep at most max_rooms
        if not rooms:
            # Default: basic apartment
            rooms = ["living", "kitchen", "bedroom", "bathroom"]

        return rooms[:self.max_rooms]

    def _extract_plot_dimensions(self, text: str, constraints: dict) -> tuple[float, float]:
        """Extract plot width and depth from text."""
        # From constraints
        if "plot_width" in constraints and "plot_depth" in constraints:
            return float(constraints["plot_width"]), float(constraints["plot_depth"])

        # From text: "10 by 15 meters", "10x15m", "10 x 15"
        patterns = [
            r"(\d+(?:\.\d+)?)\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)",
            r"(\d+(?:\.\d+)?)\s*(?:×|*)\s*(\d+(?:\.\d+)?)",
            r"plot\s+(?:size\s+)?(?:of\s+)?(\d+(?:\.\d+)?)\s*(?:x|by)\s*(\d+(?:\.\d+)?)",
            r"(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return float(match.group(1)), float(match.group(2))

        # Default
        return 15.0, 12.0

    def _extract_num_floors(self, text: str, constraints: dict) -> int:
        """Extract number of floors from text."""
        if "num_floors" in constraints:
            return int(constraints["num_floors"])

        # Check for floor mentions
        if re.search(r"\b(two|2|double|second)\s*(?:story|storey|floor|level)\b", text):
            return 2
        if re.search(r"\b(three|3|triple|third)\s*(?:story|storey|floor|level)\b", text):
            return 3
        if re.search(r"\b(single|one|1)\s*(?:story|storey|floor|level)\b", text):
            return 1
        if "basement" in text:
            return 2  # ground + basement

        return 1

    def _infer_adjacency(self, rooms: list[str], text: str) -> list[tuple[int, int]]:
        """Infer room adjacency from room types and text hints."""
        adjacency: list[tuple[int, int]] = []
        room_type_to_indices: dict[str, list[int]] = {}

        for i, room_type in enumerate(rooms):
            if room_type not in room_type_to_indices:
                room_type_to_indices[room_type] = []
            room_type_to_indices[room_type].append(i)

        # Use ADJACENCY_HINTS to connect rooms
        for room_type, indices in room_type_to_indices.items():
            hints = ADJACENCY_HINTS.get(room_type, [])
            for hint_type in hints:
                if hint_type in room_type_to_indices:
                    # Connect first instance of each type
                    src_idx = indices[0]
                    for dst_idx in room_type_to_indices[hint_type]:
                        if src_idx != dst_idx:
                            pair = (min(src_idx, dst_idx), max(src_idx, dst_idx))
                            if pair not in adjacency:
                                adjacency.append(pair)

        # Check for explicit adjacency mentions in text
        # "kitchen next to dining", "bedroom adjacent to bathroom"
        adj_patterns = [
            (r"(\w+)\s+(?:next to|adjacent to|connected to|near|beside|leading to)\s+(\w+)", 2),
            (r"(\w+)\s+(?:opens to|opens into|opening to)\s+(\w+)", 2),
            (r"(\w+)\s+(?:off|from)\s+(?:the\s+)?(\w+)", 2),
        ]

        for pattern, _ in adj_patterns:
            for match in re.finditer(pattern, text):
                word1, word2 = match.group(1), match.group(2)
                type1 = self._match_room_type(word1)
                type2 = self._match_room_type(word2)
                if type1 and type2 and type1 in room_type_to_indices and type2 in room_type_to_indices:
                    src_idx = room_type_to_indices[type1][0]
                    dst_idx = room_type_to_indices[type2][0]
                    pair = (min(src_idx, dst_idx), max(src_idx, dst_idx))
                    if pair not in adjacency:
                        adjacency.append(pair)

        return adjacency

    def _match_room_type(self, word: str) -> str | None:
        """Match a single word to a room type."""
        for room_type, keywords in ROOM_KEYWORDS.items():
            if word in keywords or word == room_type:
                return room_type
        return None

    def _extract_room_sizes(self, text: str, rooms: list[str]) -> dict[str, str]:
        """Extract size modifiers for rooms from text."""
        room_sizes: dict[str, str] = {}

        for room_type in rooms:
            # Check for size keywords near room mention
            for kw in ROOM_KEYWORDS.get(room_type, [room_type]):
                for size_kw, size_name in SIZE_KEYWORDS.items():
                    # "large living room", "spacious kitchen"
                    pattern = rf"{size_kw}\s+{kw}"
                    if re.search(pattern, text):
                        room_sizes[room_type] = size_name
                        break
                    # "living room is large"
                    pattern2 = rf"{kw}.*(?:is|should be|needs to be)\s+{size_kw}"
                    if re.search(pattern2, text):
                        room_sizes[room_type] = size_name
                        break

            # Default to medium if not specified
            if room_type not in room_sizes:
                room_sizes[room_type] = "medium"

        return room_sizes

    def get_room_areas(self, room_sizes: dict[str, str], rooms: list[str]) -> list[float]:
        """Convert size categories to actual area values."""
        areas = []
        for room_type in rooms:
            size_cat = room_sizes.get(room_type, "medium")
            area_map = SIZE_AREAS.get(size_cat, SIZE_AREAS["medium"])
            areas.append(area_map.get(room_type, 10.0))
        return areas
