"""VLM-based sketch understanding.

Extracts a structured room graph from a sketch image via hosted
vision-language models. Providers tried in order (VLM_PROVIDERS env):
  - "groq"   — Groq LPU inference, OpenAI-compatible API
  - "gemini" — Google Gemini generateContent API
  - "grok"   — xAI, OpenAI-compatible chat/completions

Falls back to returning no rooms when every provider fails or no key is
configured, so callers can degrade gracefully.
"""

import base64
import io
import json
import logging
import os
import re
from typing import Any

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

MAX_ROOMS = 20

ROOM_TYPES = [
    "living", "kitchen", "bedroom", "bathroom", "dining",
    "hallway", "entrance", "balcony", "storage", "garage",
    "office", "utility",
]

TYPE_ALIASES = {
    "living room": "living", "lounge": "living", "sitting room": "living",
    "family room": "living", "great room": "living", "parlor": "living",
    "master bedroom": "bedroom", "master": "bedroom", "guest room": "bedroom",
    "ensuite": "bathroom", "toilet": "bathroom", "wc": "bathroom",
    "washroom": "bathroom", "restroom": "bathroom", "shower room": "bathroom",
    "dining room": "dining", "breakfast room": "dining",
    "corridor": "hallway", "passage": "hallway", "passageway": "hallway",
    "foyer": "entrance", "entry": "entrance", "entryway": "entrance",
    "lobby": "entrance", "vestibule": "entrance", "genkan": "entrance",
    "pantry": "storage", "closet": "storage", "walk-in closet": "storage",
    "laundry": "utility", "laundry room": "utility", "mudroom": "utility",
    "utility room": "utility", "mechanical": "utility",
    "study": "office", "home office": "office", "den": "office",
    "studio": "office", "library": "office",
    "terrace": "balcony", "patio": "balcony", "veranda": "balcony",
    "deck": "balcony", "porch": "balcony",
    "carport": "garage", "garage parking": "garage",
}

EXTRACTION_PROMPT = f"""You are analyzing a hand-drawn or photographed floor plan sketch.

Identify every room in the sketch and output ONLY a JSON object (no markdown, no commentary) with this exact schema:

{{
  "rooms": [
    {{"type": "<room type>", "bbox": [<x>, <y>, <width>, <height>], "confidence": <0.0-1.0>}}
  ],
  "adjacency": [[<room_index_a>, <room_index_b>], ...]
}}

Rules:
- "type" must be one of: {", ".join(ROOM_TYPES)}. Pick the closest match.
- "bbox" is the room's bounding box normalized to image coordinates (0.0-1.0), origin at top-left. x,y is the top-left corner.
- Room indices in "adjacency" refer to positions in the "rooms" array (0-based). Two rooms are adjacent if they share a wall or are directly connected by a door/opening.
- Include every enclosed or labelled region you can identify, up to {MAX_ROOMS} rooms.
- If a room label is unreadable, infer the type from context (e.g. a small room off a bedroom is likely a bathroom or storage).
- If the sketch shows multiple stories, extract the ground floor only.
"""

PROVIDERS = {
    "groq": {
        "key_env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "default_model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "base_env": "GROQ_API_BASE",
        "default_base": "https://api.groq.com/openai/v1",
        "kind": "openai_compat",
    },
    "gemini": {
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-2.5-flash",
        "kind": "gemini",
    },
    "grok": {
        "key_env": "XAI_API_KEY",
        "model_env": "XAI_MODEL",
        "default_model": "grok-4-fast-non-reasoning",
        "base_env": "XAI_API_BASE",
        "default_base": "https://api.x.ai/v1",
        "kind": "openai_compat",
    },
}


class VLMSketchEncoder:
    """Extracts room graphs from sketch images via a provider chain."""

    def __init__(self, providers: str | None = None, timeout: float = 60.0):
        chain = providers or os.getenv("VLM_PROVIDERS", "groq,gemini")
        self.providers = [p.strip().lower() for p in chain.split(",") if p.strip() in PROVIDERS]
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def has_providers(self) -> bool:
        return any(os.getenv(PROVIDERS[p]["key_env"]) for p in self.providers)

    def encode(self, image_bytes: bytes) -> dict[str, Any]:
        """Return {rooms: [{type,bbox,confidence}], adjacency: [[a,b]], source}."""
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        png_b64 = self._to_png_b64(image)
        width_px, height_px = image.size

        for provider in self.providers:
            spec = PROVIDERS[provider]
            api_key = os.getenv(spec["key_env"])
            if not api_key:
                continue
            try:
                raw = self._call(provider, spec, api_key, png_b64)
                graph = self._parse_graph(raw)
                graph["source"] = f"vlm:{provider}/{os.getenv(spec['model_env']) or spec['default_model']}"
                graph["imageSize"] = {"width": width_px, "height": height_px}
                return graph
            except Exception as e:  # noqa: BLE001 — try next provider
                logger.warning("VLM provider %s failed: %s", provider, e)

        raise RuntimeError("All VLM providers failed")

    # ---- Provider calls -------------------------------------------------

    def _call(self, provider: str, spec: dict, api_key: str, png_b64: str) -> str:
        model = os.getenv(spec["model_env"]) or spec["default_model"]
        if spec["kind"] == "openai_compat":
            base = os.getenv(spec.get("base_env", ""), spec["default_base"])
            resp = self._client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0,
                    "max_completion_tokens": 1500,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": EXTRACTION_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{png_b64}", "detail": "high"},
                                },
                            ],
                        }
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        resp = self._client.post(
            url,
            headers={"x-goog-api-key": api_key},
            json={
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": "image/png", "data": png_b64}},
                    {"text": EXTRACTION_PROMPT},
                ]}],
                "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
            },
        )
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)

    # ---- Parsing ---------------------------------------------------------

    def _parse_graph(self, raw_text: str) -> dict[str, Any]:
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON in VLM response: {raw_text[:200]}")
        data = json.loads(match.group(0))
        raw_rooms = data.get("rooms", [])[:MAX_ROOMS]

        rooms = []
        for r in raw_rooms:
            bbox = self._normalize_bbox(r.get("bbox"))
            if bbox is None:
                continue
            rooms.append({
                "type": self._normalize_type(r.get("type", "")),
                "bbox": bbox,
                "confidence": float(r.get("confidence", 0.5)),
            })
        if not rooms:
            raise ValueError("VLM returned no usable rooms")

        n = len(rooms)
        adjacency = set()
        for pair in data.get("adjacency", []):
            try:
                a, b = int(pair[0]), int(pair[1])
            except (TypeError, ValueError, IndexError):
                continue
            if a != b and 0 <= a < n and 0 <= b < n:
                adjacency.add((min(a, b), max(a, b)))

        return {"rooms": rooms, "adjacency": sorted(adjacency), "num_rooms": n}

    @staticmethod
    def _normalize_type(raw: str) -> str:
        t = re.sub(r"[_\-]+", " ", str(raw).lower().strip())
        if t in ROOM_TYPES:
            return t
        if t in TYPE_ALIASES:
            return TYPE_ALIASES[t]
        for token in t.split():
            if token in ROOM_TYPES:
                return token
            if token in TYPE_ALIASES:
                return TYPE_ALIASES[token]
        return "storage"

    @staticmethod
    def _normalize_bbox(raw: Any) -> list[float] | None:
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            return None
        try:
            x, y, w, h = (float(v) for v in raw)
        except (TypeError, ValueError):
            return None
        if max(x, y, w, h) > 100:
            return None
        if max(x, y, w, h) > 1.0:
            x, y, w, h = x / 100.0, y / 100.0, w / 100.0, h / 100.0
        x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
        w = min(max(w, 0.0), 1.0 - x)
        h = min(max(h, 0.0), 1.0 - y)
        if w <= 0 or h <= 0:
            return None
        return [x, y, w, h]

    @staticmethod
    def _to_png_b64(image: Image.Image) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
