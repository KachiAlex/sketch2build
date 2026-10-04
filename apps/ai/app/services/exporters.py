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


WALL_HEIGHT = 2.8  # metres — storey height for massing/BIM exports


def _room_rect(boundary: List[Point]) -> tuple[float, float, float, float] | None:
    if len(boundary) < 3:
        return None
    xs = [float(p[0]) for p in boundary]
    ys = [float(p[1]) for p in boundary]
    return min(xs), min(ys), max(xs), max(ys)


def generate_glb(layout: Layout) -> bytes:
    """Binary glTF 2.0 massing model — each room extruded to WALL_HEIGHT."""
    import json
    import struct

    positions: list[float] = []
    indices: list[int] = []
    floors = sorted({r.get("floor", 1) for r in layout.get("rooms", [])} or {1})

    for room in layout.get("rooms", []):
        rect = _room_rect(room.get("boundaryGeometry", []))
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        z0 = (int(room.get("floor", 1)) - 1) * WALL_HEIGHT
        z1 = z0 + WALL_HEIGHT
        base = len(positions) // 3
        # glTF is right-handed, Y-up: plan (x, y) maps to (x, -z-plan).
        positions += [
            x0, z0, -y0, x1, z0, -y0, x1, z0, -y1, x0, z0, -y1,
            x0, z1, -y0, x1, z1, -y0, x1, z1, -y1, x0, z1, -y1,
        ]
        indices += [
            base + 0, base + 2, base + 1, base + 0, base + 3, base + 2,  # bottom
            base + 4, base + 5, base + 6, base + 4, base + 6, base + 7,  # top
            base + 0, base + 1, base + 5, base + 0, base + 5, base + 4,
            base + 1, base + 2, base + 6, base + 1, base + 6, base + 5,
            base + 2, base + 3, base + 7, base + 2, base + 7, base + 6,
            base + 3, base + 0, base + 4, base + 3, base + 4, base + 7,
        ]

    if not positions:
        raise RuntimeError("No room geometry to export")

    pos_bytes = struct.pack(f"<{len(positions)}f", *positions)
    idx_bytes = struct.pack(f"<{len(indices)}H", *indices)
    bin_chunk = pos_bytes + idx_bytes
    if len(bin_chunk) % 4:
        bin_chunk += b"\x00" * (4 - len(bin_chunk) % 4)

    xs = positions[0::3]
    ys = positions[1::3]
    zs = positions[2::3]
    gltf = {
        "asset": {"version": "2.0", "generator": "Sketch2Build"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "massing"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {
                "bufferView": 0, "componentType": 5126, "count": len(positions) // 3,
                "type": "VEC3", "min": [min(xs), min(ys), min(zs)], "max": [max(xs), max(ys), max(zs)],
            },
            {"bufferView": 1, "componentType": 5123, "count": len(indices), "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(pos_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(pos_bytes), "byteLength": len(idx_bytes), "target": 34963},
        ],
        "buffers": [{"byteLength": len(pos_bytes) + len(idx_bytes)}],
        "extras": {"floors": floors},
    }
    json_chunk = json.dumps(gltf, separators=(",", ":")).encode()
    if len(json_chunk) % 4:
        json_chunk += b" " * (4 - len(json_chunk) % 4)

    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    return (
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(json_chunk), 0x4E4F534A)
        + json_chunk
        + struct.pack("<II", len(bin_chunk), 0x004E4942)
        + bin_chunk
    )


_IFC_GUID_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"


def _ifc_guid(seed: int) -> str:
    """Deterministic 22-char IFC GUID (valid charset, leading char 0-3)."""
    chars = []
    n = seed * 2654435761 % (64**22)
    for _ in range(22):
        chars.append(_IFC_GUID_CHARS[n % 64])
        n //= 64
    chars[0] = "0123"[seed % 4]
    return "".join(chars)


def generate_ifc(layout: Layout) -> bytes:
    """Minimal IFC4 STEP file: one building, one storey per floor, IfcSpace per room."""
    lines: list[str] = []
    counter = [0]

    def add(entity: str) -> int:
        counter[0] += 1
        lines.append(f"#{counter[0]}={entity};")
        return counter[0]

    si_len = add("IFCSIUNIT(*,.LENGTHUNIT.,$,.METRE.)")
    si_area = add("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)")
    units = add(f"IFCUNITASSIGNMENT((#{si_len},#{si_area}))")
    origin = add("IFCCARTESIANPOINT((0.,0.,0.))")
    dir_z = add("IFCDIRECTION((0.,0.,1.))")
    dir_x = add("IFCDIRECTION((1.,0.,0.))")
    ctx3d = add(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#{origin},#{dir_x})")
    add("IFCGEOMETRICREPRESENTATIONSUBCONTEXT('Body','Model',*,*,*,*,#{$ctx},*,*,*,*,*,*,*,*,*,*,*,*)".replace("#{$ctx}", f"#{ctx3d}"))
    sub_ctx = counter[0]
    app = add("IFCAPPLICATION(#2,'0.1','Sketch2Build','S2B')")
    org = add("IFCORGANIZATION($,'Sketch2Build',$,$,$)")
    person = add("IFCPERSON($,'Sketch2Build','User',$,$,$,$,$)")
    pers_org = add(f"IFCPERSONANDORGANIZATION(#{person},#{org},$)")
    owner = add(f"IFCOWNERHISTORY(#{pers_org},#{app},$,.ADDED.,$,#{pers_org},#{app},0)")
    project_placement = add(f"IFCLOCALPLACEMENT($,#{origin})")
    axis3d = add(f"IFCAXIS2PLACEMENT3D(#{origin},#{dir_z},#{dir_x})")
    project_placement = add(f"IFCLOCALPLACEMENT($,#{axis3d})")
    project = add(
        f"IFCPROJECT('{_ifc_guid(1)}',#{owner},'Sketch2Build Layout',$,$,$,$,(#{ctx3d}),#{units})"
    )
    site_placement = add(f"IFCLOCALPLACEMENT(#{project_placement},#{axis3d})")
    site = add(f"IFCSITE('{_ifc_guid(2)}',#{owner},'Site',$,$,#{site_placement},$,$,.ELEMENT.,$,$,$,$,$)")
    bldg_placement = add(f"IFCLOCALPLACEMENT(#{site_placement},#{axis3d})")
    bldg = add(f"IFCBUILDING('{_ifc_guid(3)}',#{owner},'Building',$,$,#{bldg_placement},$,$,.ELEMENT.,$,$,$)")
    add(f"IFCRELAGGREGATES('{_ifc_guid(4)}',#{owner},$,$,#{project},(#{site}))")
    add(f"IFCRELAGGREGATES('{_ifc_guid(5)}',#{owner},$,$,#{site},(#{bldg}))")

    spaces: list[int] = []
    space_floor: dict[int, int] = {}
    seed = 100
    storey_ids: dict[int, int] = {}
    storey_placement: dict[int, int] = {}
    for room in layout.get("rooms", []):
        rect = _room_rect(room.get("boundaryGeometry", []))
        if rect is None:
            continue
        floor = int(room.get("floor", 1))
        if floor not in storey_ids:
            elev_pt = add(f"IFCCARTESIANPOINT((0.,0.,{(floor - 1) * WALL_HEIGHT}))")
            elev_pl = add(f"IFCAXIS2PLACEMENT3D(#{elev_pt},#{dir_z},#{dir_x})")
            st_pl = add(f"IFCLOCALPLACEMENT(#{bldg_placement},#{elev_pl})")
            storey_ids[floor] = add(
                f"IFCBUILDINGSTOREY('{_ifc_guid(seed)}',#{owner},'Floor {floor}',$,$,#{st_pl},$,$,.ELEMENT.,{(floor - 1) * WALL_HEIGHT})"
            )
            storey_placement[floor] = st_pl
            seed += 1
            add(
                f"IFCRELAGGREGATES('{_ifc_guid(seed)}',#{owner},$,$,#{bldg},(#{storey_ids[floor]}))"
            )
            seed += 1

        x0, y0, x1, y1 = rect
        w, h = x1 - x0, y1 - y0
        pt = add(f"IFCCARTESIANPOINT(({x0},{y0},0.))")
        placement3d = add(f"IFCAXIS2PLACEMENT3D(#{pt},#{dir_z},#{dir_x})")
        local = add(f"IFCLOCALPLACEMENT(#{storey_placement[floor]},#{placement3d})")
        profile_pt = add(f"IFCCARTESIANPOINT(({w / 2},{h / 2},0.))")
        profile_pl = add(f"IFCAXIS2PLACEMENT2D(#{profile_pt},$)")
        profile = add(f"IFCRECTANGLEPROFILEDEF(.AREA.,'Room',#{profile_pl},{w},{h})")
        solid = add(f"IFCEXTRUDEDAREASOLID(#{profile},#{axis3d},#{dir_z},{WALL_HEIGHT})")
        rep = add(f"IFCSHAPEREPRESENTATION(#{sub_ctx},'Body','SweptSolid',(#{solid}))")
        shape = add(f"IFCPRODUCTDEFINITIONSHAPE($,$,(#{rep}))")
        name = (room.get("label") or room.get("type") or "Room").replace("'", "")
        space = add(
            f"IFCSPACE('{_ifc_guid(seed)}',#{owner},'{name}',$,$,#{local},#{shape},$,.ELEMENT.,$)"
        )
        spaces.append(space)
        space_floor[space] = floor
        seed += 1

    for floor, sid in storey_ids.items():
        floor_spaces = [s for s in spaces if space_floor[s] == floor]
        if floor_spaces:
            add(
                f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{_ifc_guid(seed)}',#{owner},$,$,({','.join(f'#{s}' for s in floor_spaces)}),#{sid})"
            )
            seed += 1

    header = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');\n"
        "FILE_NAME('layout.ifc','2026-01-01T00:00:00',('Sketch2Build'),(''),'','Sketch2Build','');\n"
        "FILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
    )
    return (header + "\n".join(lines) + "\nENDSEC;\nEND-ISO-10303-21;\n").encode()


def generate_3d_massing(layout: Layout) -> bytes:
    """3D massing model — returns a GLB binary (was a JSON stub)."""
    return generate_glb(layout)


def _centroid(points: List[Point]) -> Point:
    n = len(points)
    cx = sum(p[0] for p in points) / n
    cy = sum(p[1] for p in points) / n
    return [cx, cy]
