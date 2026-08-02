"""DXF (AutoCAD Drawing Exchange Format) export.

Generates 2D and 3D DXF files from floor plan geometry for CAD workflows.
Uses a lightweight DXF writer (no external library dependency)."""

import structlog
from typing import Any
from pathlib import Path
from datetime import datetime

from src.models.massing.extruder import Building3D, Room3D, Wall3D

logger = structlog.get_logger()


class DXFExporter:
    """Export building geometry to DXF format."""

    def __init__(self, version: str = "AC1015"):
        self.version = version  # R2000

    def _header(self) -> list[str]:
        return [
            "0", "SECTION",
            "2", "HEADER",
            "9", "$ACADVER",
            "1", self.version,
            "9", "$INSUNITS",
            "70", "6",  # Meters
            "0", "ENDSEC",
        ]

    def _classes(self) -> list[str]:
        return [
            "0", "SECTION",
            "2", "CLASSES",
            "0", "ENDSEC",
        ]

    def _tables(self) -> list[str]:
        return [
            "0", "SECTION",
            "2", "TABLES",
            "0", "TABLE",
            "2", "LTYPE",
            "5", "5",
            "100", "AcDbSymbolTable",
            "70", "2",
            "0", "LTYPE",
            "5", "14",
            "100", "AcDbSymbolTableRecord",
            "100", "AcDbLinetypeTableRecord",
            "2", "CONTINUOUS",
            "70", "0",
            "3", "Solid line",
            "72", "65",
            "73", "0",
            "40", "0.0",
            "0", "ENDTAB",
            "0", "TABLE",
            "2", "LAYER",
            "5", "2",
            "100", "AcDbSymbolTable",
            "70", "3",
            "0", "LAYER",
            "5", "10",
            "100", "AcDbSymbolTableRecord",
            "100", "AcDbLayerTableRecord",
            "2", "WALLS",
            "70", "0",
            "62", "7",
            "6", "CONTINUOUS",
            "0", "LAYER",
            "5", "11",
            "100", "AcDbSymbolTableRecord",
            "100", "AcDbLayerTableRecord",
            "2", "ROOMS",
            "70", "0",
            "62", "1",
            "6", "CONTINUOUS",
            "0", "LAYER",
            "5", "12",
            "100", "AcDbSymbolTableRecord",
            "100", "AcDbLayerTableRecord",
            "2", "DOORS",
            "70", "0",
            "62", "3",
            "6", "CONTINUOUS",
            "0", "ENDTAB",
            "0", "ENDSEC",
        ]

    def _blocks(self) -> list[str]:
        return [
            "0", "SECTION",
            "2", "BLOCKS",
            "0", "ENDSEC",
        ]

    def _polyline_2d(self, points: list[tuple[float, float]], layer: str = "WALLS", closed: bool = True) -> list[str]:
        """Generate 2D polyline entity."""
        lines = [
            "0", "LWPOLYLINE",
            "5", "100",
            "100", "AcDbEntity",
            "8", layer,
            "100", "AcDbPolyline",
            "90", str(len(points)),
            "70", "1" if closed else "0",
            "43", "0.0",
        ]
        for x, y in points:
            lines.extend(["10", str(x), "20", str(y)])
        return lines

    def _line_3d(self, x1: float, y1: float, z1: float, x2: float, y2: float, z2: float, layer: str = "WALLS") -> list[str]:
        """Generate 3D line entity."""
        return [
            "0", "LINE",
            "5", "100",
            "100", "AcDbEntity",
            "8", layer,
            "100", "AcDbLine",
            "10", str(x1), "20", str(y1), "30", str(z1),
            "11", str(x2), "21", str(y2), "31", str(z2),
        ]

    def _text(self, x: float, y: float, text: str, layer: str = "ROOMS", height: float = 0.3) -> list[str]:
        """Generate text entity."""
        return [
            "0", "TEXT",
            "5", "100",
            "100", "AcDbEntity",
            "8", layer,
            "100", "AcDbText",
            "10", str(x), "20", str(y), "30", "0.0",
            "40", str(height),
            "1", text,
            "100", "AcDbText",
        ]

    def _room_2d(self, room: Room3D) -> list[str]:
        """Generate 2D DXF entities for a room."""
        lines = []
        x, y = room.x, room.y
        w, d = room.width, room.depth

        # Room outline (wall lines)
        lines.extend(self._polyline_2d([
            (x, y), (x + w, y), (x + w, y + d), (x, y + d),
        ], layer="WALLS", closed=True))

        # Room label
        lines.extend(self._text(
            x + w / 2, y + d / 2,
            f"{room.type}",
            layer="ROOMS",
            height=min(w, d) / 10,
        ))

        return lines

    def _room_3d(self, room: Room3D) -> list[str]:
        """Generate 3D DXF entities for a room (walls as edges)."""
        lines = []
        x, y, z = room.x, room.y, room.z
        w, d, h = room.width, room.depth, room.height

        # Bottom face edges
        bottom = [(x, y, z), (x + w, y, z), (x + w, y + d, z), (x, y + d, z)]
        # Top face edges
        top = [(x, y, z + h), (x + w, y, z + h), (x + w, y + d, z + h), (x, y + d, z + h)]

        # Bottom rectangle
        for i in range(4):
            j = (i + 1) % 4
            lines.extend(self._line_3d(bottom[i][0], bottom[i][1], bottom[i][2],
                                        bottom[j][0], bottom[j][1], bottom[j][2], layer="WALLS"))

        # Top rectangle
        for i in range(4):
            j = (i + 1) % 4
            lines.extend(self._line_3d(top[i][0], top[i][1], top[i][2],
                                        top[j][0], top[j][1], top[j][2], layer="WALLS"))

        # Vertical edges (wall corners)
        for i in range(4):
            lines.extend(self._line_3d(bottom[i][0], bottom[i][1], bottom[i][2],
                                        top[i][0], top[i][1], top[i][2], layer="WALLS"))

        # Room label (at mid height)
        lines.extend(self._text(
            x + w / 2, y + d / 2,
            f"{room.type}",
            layer="ROOMS",
            height=min(w, d) / 10,
        ))

        # Door openings (if any)
        for opening in room.openings:
            if opening.get("type") == "door":
                ox, oy = opening.get("x", x + w / 2), opening.get("y", y + d / 2)
                lines.extend(self._line_3d(
                    ox, oy, z,
                    ox, oy, z + opening.get("height", 2.1),
                    layer="DOORS",
                ))

        return lines

    def export_2d(self, building: Building3D, output_path: str) -> str:
        """Export 2D floor plan to DXF."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.extend(self._header())
        lines.extend(self._classes())
        lines.extend(self._tables())
        lines.extend(self._blocks())

        # Entities section
        lines.extend(["0", "SECTION", "2", "ENTITIES"])

        for room in building.rooms:
            lines.extend(self._room_2d(room))

        lines.extend(["0", "ENDSEC"])
        lines.append("0")
        lines.append("EOF")

        dxf_content = "\n".join(lines)
        output_path.write_text(dxf_content, encoding="utf-8")

        logger.info("2D DXF exported", path=str(output_path), rooms=len(building.rooms))
        return str(output_path)

    def export_3d(self, building: Building3D, output_path: str) -> str:
        """Export 3D model to DXF."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = []
        lines.extend(self._header())
        lines.extend(self._classes())
        lines.extend(self._tables())
        lines.extend(self._blocks())

        # Entities section
        lines.extend(["0", "SECTION", "2", "ENTITIES"])

        for room in building.rooms:
            lines.extend(self._room_3d(room))

        lines.extend(["0", "ENDSEC"])
        lines.append("0")
        lines.append("EOF")

        dxf_content = "\n".join(lines)
        output_path.write_text(dxf_content, encoding="utf-8")

        logger.info("3D DXF exported", path=str(output_path), rooms=len(building.rooms))
        return str(output_path)
