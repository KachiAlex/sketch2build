from __future__ import annotations
import io
from typing import Any, Dict, List

try:
    import ezdxf
except ImportError:  # pragma: no cover
    ezdxf = None  # type: ignore

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
except ImportError:  # pragma: no cover
    canvas = None  # type: ignore
    A4 = None  # type: ignore

from PIL import Image, ImageDraw


Point = List[float]
Layout = Dict[str, Any]


def _room_boundaries(layout: Layout) -> List[List[Point]]:
    rooms = layout.get("rooms", [])
    boundaries = []
    for room in rooms:
        boundary = room.get("boundaryGeometry")
        if boundary and len(boundary) >= 3:
            boundaries.append(boundary)
    return boundaries


def generate_dxf(layout: Layout) -> bytes:
    """Generate a DXF drawing with rooms on a 'ROOMS' layer."""
    if ezdxf is None:
        raise RuntimeError("ezdxf is not installed")
    doc = ezdxf.new()
    doc.header["$INSUNITS"] = 6  # metres
    msp = doc.modelspace()
    rooms_layer = doc.layers.add("ROOMS")
    rooms_layer.color = 5

    for room in layout.get("rooms", []):
        boundary = room.get("boundaryGeometry", [])
        if len(boundary) < 3:
            continue
        points = [(float(p[0]), float(p[1])) for p in boundary]
        msp.add_lwpolyline(points + [points[0]], close=True, dxfattribs={"layer": "ROOMS"})

    stream = io.BytesIO()
    doc.saveas(stream)
    return stream.getvalue()


def generate_png(layout: Layout, width: int = 800, height: int = 800) -> bytes:
    """Render an orthographic PNG of the layout."""
    boundaries = _room_boundaries(layout)
    if not boundaries:
        return b""

    all_points = [p for boundary in boundaries for p in boundary]
    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    span_x = max_x - min_x or 1.0
    span_y = max_y - min_y or 1.0
    padding = max(span_x, span_y) * 0.1

    def transform(point: Point) -> tuple[int, int]:
        x = (point[0] - min_x + padding) / (span_x + 2 * padding) * width
        y = height - (point[1] - min_y + padding) / (span_y + 2 * padding) * height
        return int(x), int(y)

    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    for room in layout.get("rooms", []):
        boundary = room.get("boundaryGeometry", [])
        if len(boundary) < 3:
            continue
        pts = [transform(p) for p in boundary]
        draw.polygon(pts, outline="black", fill="#e5e7eb")
        centroid = _centroid(boundary)
        cx, cy = transform(centroid)
        label = room.get("label") or room.get("type", "Room")
        draw.text((cx - 20, cy - 5), label, fill="black")

    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def generate_pdf(layout: Layout) -> bytes:
    """Generate a simple presentation PDF with dimensions and labels."""
    if canvas is None or A4 is None:
        raise RuntimeError("reportlab is not installed")
    stream = io.BytesIO()
    c = canvas.Canvas(stream, pagesize=A4)
    width, height = A4

    boundaries = _room_boundaries(layout)
    if boundaries:
        all_points = [p for boundary in boundaries for p in boundary]
        xs = [p[0] for p in all_points]
        ys = [p[1] for p in all_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max_x - min_x or 1.0
        span_y = max_y - min_y or 1.0
        margin = 72
        draw_w = width - 2 * margin
        draw_h = height - 2 * margin - 60
        scale = min(draw_w / span_x, draw_h / span_y) * 0.9

        def tx(x: float, y: float) -> tuple[float, float]:
            return margin + (x - min_x) * scale, height - margin - 30 - (y - min_y) * scale

        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, height - 40, "Sketch2Build Layout")
        for room in layout.get("rooms", []):
            boundary = room.get("boundaryGeometry", [])
            if len(boundary) < 3:
                continue
            path = c.beginPath()
            for i, p in enumerate(boundary):
                x, y = tx(p[0], p[1])
                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            path.close()
            c.drawPath(path, stroke=1, fill=0)
            cx, cy = tx(*_centroid(boundary))
            c.setFont("Helvetica", 9)
            c.drawCentredString(cx, cy, room.get("label") or room.get("type", "Room"))

    c.save()
    return stream.getvalue()


def generate_ifc(layout: Layout) -> Dict[str, Any]:
    """Placeholder IFC/BIM export."""
    return {
        "format": "IFC",
        "status": "stub",
        "message": "IFC export requires ifcopenshell; integration scheduled for Phase 6.2.",
        "room_count": len(layout.get("rooms", [])),
    }


def generate_3d_massing(layout: Layout) -> Dict[str, Any]:
    """Placeholder 3D massing model."""
    return {
        "format": "glTF",
        "status": "stub",
        "message": "3D massing model generation scheduled for Phase 6.4.",
        "extruded_rooms": len(layout.get("rooms", [])),
    }


def _centroid(points: List[Point]) -> Point:
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    return [cx, cy]
