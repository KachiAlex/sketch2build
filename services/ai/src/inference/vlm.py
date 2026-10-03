"""VLM-based sketch understanding module.

Extracts a structured room graph from a sketch image using a hosted
vision-language model instead of the locally fine-tuned CLIP encoder.
Returns the same graph dict shape as `vision.SketchEncoder` so it drops
into DesignPipeline unchanged.

Providers (tried in order, then the local encoder as final fallback):
  - "grok"   — xAI, OpenAI-compatible chat/completions (api.x.ai)
  - "groq"   — Groq (groq.com) LPU inference, OpenAI-compatible
  - "gemini" — Google Gemini generateContent API

Set VISION_BACKEND=vlm and VLM_PROVIDERS="grok,gemini" to enable.
"""

import base64
import io
import json
import re
from typing import Any

import httpx
import structlog
from PIL import Image

from src.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

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

DEFAULT_MODELS = {
    "grok": "grok-4-fast-non-reasoning",
    "gemini": "gemini-3.8-flash",
}

# provider -> (key attr, model attr, default model, api kind, base attr)
PROVIDERS = {
    "grok": ("xai_api_key", "grok_model", DEFAULT_MODELS["grok"], "openai_compat", "xai_api_base"),
    "groq": ("groq_api_key", "groq_model", "qwen/qwen3.8-27b", "openai_compat", "groq_api_base"),
    "gemini": ("gemini_api_key", "gemini_model", "gemini-3.8-flash", "gemini", None),
}


class VLMSketchEncoder:
    """Encodes architectural sketches into structured room graphs via VLMs.

    Tries each configured provider in order (settings.vlm_providers or an
    explicit `provider` override), then the local fine-tuned/placeholder
    SketchEncoder as the final fallback.

    Args:
        provider: comma-separated provider chain, e.g. "grok,gemini"
                  (defaults to settings.vlm_providers)
        model: override the model name for the first provider in the chain
        fallback_to_local: fall back to the local SketchEncoder when every
            VLM provider fails (default settings.vlm_fallback_to_local)
    """

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        fallback_to_local: bool | None = None,
        timeout: float | None = None,
    ):
        chain = provider if provider else settings.vlm_providers
        self.providers = [p.strip().lower() for p in chain.split(",") if p.strip()]
        for p in self.providers:
            if p not in PROVIDERS:
                raise ValueError(
                    f"Unknown VLM provider '{p}'. Choose from: {list(PROVIDERS)}"
                )
        if not self.providers:
            raise ValueError("Empty VLM provider chain")

        self.models = {}
        self.api_keys = {}
        for i, p in enumerate(self.providers):
            key_attr, model_attr, default_model, _, _ = PROVIDERS[p]
            # --model override applies to the first provider in the chain
            self.models[p] = (model if i == 0 and model else None) or getattr(
                settings, model_attr
            ) or default_model
            self.api_keys[p] = getattr(settings, key_attr)

        self.timeout = timeout or settings.vlm_timeout
        self.fallback_to_local = (
            settings.vlm_fallback_to_local if fallback_to_local is None else fallback_to_local
        )
        self._fallback = None  # lazy — CLIP weights are heavy
        self._client = httpx.Client(timeout=self.timeout)

        usable = [p for p in self.providers if self.api_keys[p]]
        if not usable:
            if self.fallback_to_local:
                logger.warning(
                    "No API key for any VLM provider; will use local encoder",
                    providers=self.providers,
                )
            else:
                raise ValueError(
                    f"No API key configured for any of {self.providers}; "
                    "set one in .env or enable vlm_fallback_to_local."
                )
        logger.info(
            "VLMSketchEncoder initialized", chain=self.providers, usable=usable
        )

    def encode(self, base64_image: str) -> dict[str, Any]:
        """Decode base64 sketch image and extract structured room graph."""
        image = self._decode_image(base64_image)
        png_b64 = self._to_png_b64(image)

        for provider in self.providers:
            api_key = self.api_keys[provider]
            if not api_key:
                logger.warning("No API key, skipping provider", provider=provider)
                continue
            try:
                raw_text = self._call_provider(provider, png_b64)
                graph = self._parse_graph(raw_text)
                graph["source"] = f"vlm:{provider}/{self.models[provider]}"
                logger.info(
                    "VLM extracted room graph",
                    provider=provider,
                    model=self.models[provider],
                    rooms=graph["num_rooms"],
                )
                return graph
            except Exception as e:
                logger.warning(
                    "VLM provider failed, trying next",
                    provider=provider,
                    error=str(e),
                )

        return self._encode_fallback(base64_image)

    # ---- Provider calls -------------------------------------------------

    def _call_provider(self, provider: str, png_b64: str) -> str:
        kind = PROVIDERS[provider][3]
        if kind == "openai_compat":
            return self._call_openai_compat(provider, png_b64)
        return self._call_gemini(provider, png_b64)

    def _call_openai_compat(self, provider: str, png_b64: str) -> str:
        """OpenAI-compatible chat/completions with image input (xAI, Groq)."""
        api_base = getattr(settings, PROVIDERS[provider][4])
        resp = self._client.post(
            f"{api_base}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_keys[provider]}"},
            json={
                "model": self.models[provider],
                "temperature": 0,
                # Groq free tier enforces OTPM=1000; uncapped requests are
                # billed at the model's max output and rejected up front.
                "max_completion_tokens": 900,
                "response_format": {"type": "json_object"},
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": EXTRACTION_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{png_b64}",
                                    "detail": "high",
                                },
                            },
                        ],
                    }
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _call_gemini(self, provider: str, png_b64: str) -> str:
        """Gemini generateContent with inline image data."""
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.models[provider]}:generateContent"
        )
        resp = self._client.post(
            url,
            headers={"x-goog-api-key": self.api_keys[provider]},
            json={
                "contents": [
                    {
                        "parts": [
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": png_b64,
                                }
                            },
                            {"text": EXTRACTION_PROMPT},
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)

    # ---- Response parsing -----------------------------------------------

    def _parse_graph(self, raw_text: str) -> dict[str, Any]:
        """Parse and normalize the VLM's JSON into the pipeline graph format."""
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in VLM response: {raw_text[:200]}")

        data = json.loads(match.group(0))
        raw_rooms = data.get("rooms", [])[:MAX_ROOMS]

        rooms, room_types, bboxes = [], [], []
        for r in raw_rooms:
            bbox = self._normalize_bbox(r.get("bbox"))
            if bbox is None:
                continue
            rtype = self._normalize_type(r.get("type", ""))
            rooms.append(
                {
                    "type": rtype,
                    "bbox": bbox,
                    "confidence": float(r.get("confidence", 0.5)),
                }
            )
            room_types.append(rtype)
            bboxes.append(bbox)

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

        return {
            "room_types": room_types,
            "bboxes": bboxes,
            "adjacency": sorted(adjacency),
            "rooms": rooms,
            "num_rooms": n,
        }

    @staticmethod
    def _normalize_type(raw: str) -> str:
        t = re.sub(r"[_\-]+", " ", str(raw).lower().strip())
        if t in ROOM_TYPES:
            return t
        if t in TYPE_ALIASES:
            return TYPE_ALIASES[t]
        # try "master bedroom ensuite" style compounds
        for token in t.split():
            if token in ROOM_TYPES:
                return token
            if token in TYPE_ALIASES:
                return TYPE_ALIASES[token]
        logger.warning("Unknown room type from VLM, keeping raw value", raw_type=raw)
        return t or "storage"

    @staticmethod
    def _normalize_bbox(raw: Any) -> list[float] | None:
        if not isinstance(raw, (list, tuple)) or len(raw) != 4:
            return None
        try:
            x, y, w, h = (float(v) for v in raw)
        except (TypeError, ValueError):
            return None
        # tolerate 0-100 percent outputs by rescaling into 0-1
        vals = [x, y, w, h]
        if max(vals) > 100:
            return None
        if max(vals) > 1.0:
            x, y, w, h = x / 100.0, y / 100.0, w / 100.0, h / 100.0
        x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
        w = min(max(w, 0.0), 1.0 - x)
        h = min(max(h, 0.0), 1.0 - y)
        if w <= 0 or h <= 0:
            return None
        return [x, y, w, h]

    # ---- Fallback & image helpers ---------------------------------------

    def _encode_fallback(self, base64_image: str) -> dict[str, Any]:
        if not self.fallback_to_local:
            raise RuntimeError("All VLM providers failed and fallback is disabled")
        if self._fallback is None:
            try:
                from src.inference.vision import SketchEncoder
            except ImportError as e:
                raise RuntimeError(
                    "All VLM providers failed and local encoder unavailable"
                ) from e
            self._fallback = SketchEncoder()
            logger.info("Loaded local SketchEncoder as fallback")
        return self._fallback.encode(base64_image)

    @staticmethod
    def _decode_image(base64_image: str) -> Image.Image:
        """Decode base64 string (with or without data-URI header) to PIL Image."""
        _, _, data = base64_image.partition(",")
        if not data:
            data = base64_image
        image_bytes = base64.b64decode(data)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")

    @staticmethod
    def _to_png_b64(image: Image.Image) -> str:
        """Normalize any input image to PNG base64 for provider requests."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
