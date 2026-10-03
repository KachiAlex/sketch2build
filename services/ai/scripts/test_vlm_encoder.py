"""Test script for the VLM sketch encoder.

Extracts a room graph from a sketch image via a hosted vision-language
model (Grok or Gemini). Requires the provider API key in .env.

Usage:
    python -m scripts.test_vlm_encoder --image path/to/sketch.png
    python -m scripts.test_vlm_encoder --image sketch.png --provider gemini
    python -m scripts.test_vlm_encoder            # uses a generated test sketch
"""

import argparse
import base64
import io
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.inference.vlm import PROVIDERS, VLMSketchEncoder


def create_test_sketch() -> str:
    """Create a labelled test sketch as base64 (same layout as test_pipeline)."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)

    draw.rectangle([50, 50, 350, 250], outline="black", width=3)
    draw.line([200, 50, 200, 150], fill="black", width=2)
    draw.line([50, 150, 200, 150], fill="black", width=2)
    draw.line([200, 150, 350, 150], fill="black", width=2)
    draw.rectangle([195, 148, 205, 152], fill="white")
    draw.rectangle([95, 148, 105, 152], fill="white")

    draw.text((70, 90), "LIV", fill="black")
    draw.text((230, 90), "KIT", fill="black")
    draw.text((80, 190), "BED", fill="black")
    draw.text((240, 190), "BATH", fill="black")

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def main():
    parser = argparse.ArgumentParser(description="Test VLM sketch extraction")
    parser.add_argument("--image", help="Path to sketch image (PNG/JPG)")
    parser.add_argument(
        "--provider",
        help=f"VLM provider or comma chain ({', '.join(PROVIDERS)})",
    )
    parser.add_argument("--model", help="Override provider model name")
    parser.add_argument("--json", action="store_true", help="Print raw graph JSON")
    args = parser.parse_args()

    if args.image:
        b64 = base64.b64encode(Path(args.image).read_bytes()).decode()
        print(f"Loaded image: {args.image}")
    else:
        b64 = create_test_sketch()
        print("Using generated test sketch (4 labelled rooms)")

    encoder = VLMSketchEncoder(provider=args.provider, model=args.model)
    graph = encoder.encode(b64)

    print(f"\nSource: {graph['source']}")
    print(f"Rooms detected: {graph['num_rooms']}")
    for i, room in enumerate(graph["rooms"]):
        x, y, w, h = room["bbox"]
        print(
            f"  [{i}] {room['type']:<10} "
            f"bbox=({x:.2f},{y:.2f} {w:.2f}x{h:.2f}) "
            f"conf={room.get('confidence', 0):.2f}"
        )
    print(f"Adjacency: {graph['adjacency']}")

    if args.json:
        print("\n" + json.dumps(graph, indent=2))


if __name__ == "__main__":
    main()
