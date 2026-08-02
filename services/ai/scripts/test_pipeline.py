"""End-to-end test script for the AI design pipeline.

Tests both sketch-based and prompt-based design generation without requiring
a GPU or trained model checkpoints. Uses procedural fallbacks.

Usage:
    python -m scripts.test_pipeline
"""

import asyncio
import base64
import io
import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.inference.pipeline import DesignPipeline


def create_test_sketch() -> str:
    """Create a simple test sketch image as base64."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)

    # Draw simple floor plan outline
    draw.rectangle([50, 50, 350, 250], outline="black", width=3)

    # Draw internal walls
    draw.line([200, 50, 200, 150], fill="black", width=2)
    draw.line([50, 150, 200, 150], fill="black", width=2)
    draw.line([200, 150, 350, 150], fill="black", width=2)

    # Draw door openings (gaps in walls)
    draw.rectangle([195, 148, 205, 152], fill="white")
    draw.rectangle([95, 148, 105, 152], fill="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_prompt_based_generation():
    """Test design generation from text prompt."""
    print("\n" + "=" * 60)
    print("TEST 1: Prompt-Based Design Generation")
    print("=" * 60)

    prompt = "A modern 2-bedroom apartment with a spacious living room, kitchen, dining area, and 2 bathrooms. 10 by 15 meters plot."
    constraints = {
        "plot_width": 15.0,
        "plot_depth": 12.0,
        "region_key": "us_default",
    }

    pipeline = DesignPipeline()
    result = pipeline.run(
        job_id="test_prompt_001",
        input_type="text",
        sketch_image=None,
        description=prompt,
        constraints=constraints,
        style="modern",
        compliance_standard="IBC",
        generate_alternatives=2,
    )

    print(f"\nStatus: {result['status']}")
    print(f"Alternatives generated: {len(result['alternatives'])}")

    if result.get("floor_plan"):
        fp = result["floor_plan"]
        print(f"Rooms: {len(fp.get('rooms', []))}")
        for room in fp.get("rooms", []):
            print(f"  - {room.get('type')}: {room.get('area', 0):.1f} sqm ({room.get('w', 0):.1f}x{room.get('d', 0):.1f}m)")

    if result.get("compliance"):
        comp = result["compliance"]
        print(f"Compliance score: {comp.get('score', 0)*100:.0f}%")
        print(f"Violations: {len(comp.get('violations', []))}")

    if result.get("three_d_model"):
        td = result["three_d_model"]
        print(f"3D model: {td.get('room_count', 0)} rooms, {td.get('total_floor_area', 0):.1f} sqm, {td.get('total_volume', 0):.1f} m³")

    if result.get("explainability"):
        exp = result["explainability"]
        print(f"Explainability: {len(exp.get('explanations', []))} explanations")
        if exp.get("design_strengths"):
            print(f"  Strengths: {exp['design_strengths'][:2]}")
        if exp.get("recommendations"):
            print(f"  Recommendations: {exp['recommendations'][:2]}")

    return result


def test_sketch_based_generation():
    """Test design generation from sketch image."""
    print("\n" + "=" * 60)
    print("TEST 2: Sketch-Based Design Generation")
    print("=" * 60)

    sketch_b64 = create_test_sketch()
    constraints = {
        "plot_width": 15.0,
        "plot_depth": 12.0,
    }

    pipeline = DesignPipeline()
    result = pipeline.run(
        job_id="test_sketch_001",
        input_type="sketch",
        sketch_image=sketch_b64,
        description=None,
        constraints=constraints,
        style="modern",
        compliance_standard="IBC",
        generate_alternatives=2,
    )

    print(f"\nStatus: {result['status']}")
    print(f"Alternatives generated: {len(result['alternatives'])}")

    if result.get("floor_plan"):
        fp = result["floor_plan"]
        print(f"Source: {fp.get('source', 'unknown')}")
        print(f"Rooms: {len(fp.get('rooms', []))}")
        for room in fp.get("rooms", []):
            print(f"  - {room.get('type')}: {room.get('area', 0):.1f} sqm")

    if result.get("compliance"):
        comp = result["compliance"]
        print(f"Compliance score: {comp.get('score', 0)*100:.0f}%")

    return result


def test_regional_profiles():
    """Test design generation with different regional profiles."""
    print("\n" + "=" * 60)
    print("TEST 3: Regional Profile - Middle East")
    print("=" * 60)

    prompt = "A family house with living room, kitchen, 2 bedrooms, 2 bathrooms, dining, and prayer room."
    constraints = {
        "plot_width": 20.0,
        "plot_depth": 15.0,
        "region_key": "middle_east",
    }

    pipeline = DesignPipeline()
    result = pipeline.run(
        job_id="test_regional_me",
        input_type="text",
        sketch_image=None,
        description=prompt,
        constraints=constraints,
        style="mediterranean",
        compliance_standard="GCC",
        generate_alternatives=1,
    )

    print(f"\nStatus: {result['status']}")
    if result.get("floor_plan"):
        fp = result["floor_plan"]
        print(f"Rooms: {len(fp.get('rooms', []))}")
        for room in fp.get("rooms", []):
            print(f"  - {room.get('type')}: {room.get('area', 0):.1f} sqm, height={room.get('height', 0):.1f}m")

    return result


def test_text_parser():
    """Test the text-to-graph parser directly."""
    print("\n" + "=" * 60)
    print("TEST 4: Text-to-Graph Parser")
    print("=" * 60)

    from src.inference.text_parser import TextToGraphParser

    parser = TextToGraphParser()

    test_prompts = [
        "A modern 3-bedroom house with large living room, kitchen, 2 bathrooms, and a 2-car garage. 15x20 meters.",
        "Scandinavian style apartment with two bedrooms, open plan kitchen and dining, and a cozy living room.",
        "Traditional Japanese house with genkan entrance, tatami bedroom, kitchen, and bathroom.",
    ]

    for prompt in test_prompts:
        print(f"\nPrompt: {prompt}")
        result = parser.parse(prompt)
        print(f"  Rooms: {result['room_types']}")
        print(f"  Style: {result['style']}")
        print(f"  Plot: {result['dimensions']['plot_width']}x{result['dimensions']['plot_depth']}m")
        print(f"  Floors: {result['dimensions']['num_floors']}")
        print(f"  Adjacency: {result['adjacency']}")
        print(f"  Sizes: {result['room_sizes']}")


def main():
    print("=" * 60)
    print("Sketch2Build AI Pipeline - End-to-End Test")
    print("=" * 60)

    # Test text parser
    test_text_parser()

    # Test prompt-based generation
    prompt_result = test_prompt_based_generation()

    # Test sketch-based generation
    sketch_result = test_sketch_based_generation()

    # Test regional profile
    regional_result = test_regional_profiles()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)
    print(f"  Prompt test: {'PASS' if prompt_result.get('status') == 'completed' else 'FAIL'}")
    print(f"  Sketch test: {'PASS' if sketch_result.get('status') == 'completed' else 'FAIL'}")
    print(f"  Regional test: {'PASS' if regional_result.get('status') == 'completed' else 'FAIL'}")


if __name__ == "__main__":
    main()
