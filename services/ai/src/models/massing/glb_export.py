"""GLB (GL Transmission Format, Binary) export for WebGL visualization.

Generates compact binary GLB files from 3D building geometry that can be
loaded directly into Three.js, Babylon.js, or any WebGL renderer.
"""

import struct
import json
import structlog
from typing import Any
from pathlib import Path
import numpy as np

from src.models.massing.extruder import Building3D, Room3D

logger = structlog.get_logger()


class GLBExporter:
    """Export 3D building geometry to GLB (binary GLTF) format."""

    GLTF_MAGIC = b"glTF"
    GLTF_VERSION = 2
    CHUNK_TYPE_JSON = 0x4E4F534A
    CHUNK_TYPE_BIN = 0x004E4942

    def __init__(self):
        self.buffer_data = bytearray()

    def _pad_json(self, data: bytes) -> bytes:
        """Pad JSON chunk to 4-byte alignment with spaces."""
        padding = (4 - (len(data) % 4)) % 4
        return data + b" " * padding

    def _pad_bin(self, data: bytes) -> bytes:
        """Pad BIN chunk to 4-byte alignment with zeros."""
        padding = (4 - (len(data) % 4)) % 4
        return data + b"\x00" * padding

    def _append_vertices(self, vertices: np.ndarray, indices: np.ndarray) -> tuple[int, int, int]:
        """
        Append vertices and indices to buffer. Returns (byte_offset, byte_length, index_offset).
        """
        byte_offset = len(self.buffer_data)

        # Convert to float32 and uint16
        vertex_bytes = vertices.astype(np.float32).tobytes()
        index_bytes = indices.astype(np.uint16).tobytes()

        self.buffer_data.extend(vertex_bytes)
        self.buffer_data.extend(index_bytes)

        return byte_offset, len(vertex_bytes) + len(index_bytes), len(vertex_bytes) // (len(vertices) * 4)

    def _build_room_mesh(self, room: Room3D, mesh_index: int) -> dict[str, Any]:
        """Build a GLTF mesh for a single room."""
        x, y, z = room.x, room.y, room.z
        w, d, h = room.width, room.depth, room.height

        # 8 vertices of the room box
        vertices = np.array([
            [x, y, z], [x + w, y, z], [x + w, y + d, z], [x, y + d, z],  # bottom
            [x, y, z + h], [x + w, y, z + h], [x + w, y + d, z + h], [x, y + d, z + h],  # top
        ], dtype=np.float32)

        # 12 triangles (2 per face, 6 faces)
        indices = np.array([
            # Bottom (clockwise from bottom view)
            0, 2, 1, 0, 3, 2,
            # Top (counter-clockwise from top view)
            4, 5, 6, 4, 6, 7,
            # Front (y=0)
            0, 1, 5, 0, 5, 4,
            # Back (y=d)
            2, 3, 7, 2, 7, 6,
            # Left (x=0)
            0, 4, 7, 0, 7, 3,
            # Right (x=w)
            1, 2, 6, 1, 6, 5,
        ], dtype=np.uint16)

        # Normals (one per face, not vertex - simplified)
        normals = np.array([
            [0, 0, -1], [0, 0, -1], [0, 0, -1], [0, 0, -1],
            [0, 0, 1], [0, 0, 1], [0, 0, 1], [0, 0, 1],
        ], dtype=np.float32)

        # Combine position + normal
        vertex_data = np.hstack([vertices, normals])

        byte_offset = len(self.buffer_data)
        vertex_bytes = vertex_data.astype(np.float32).tobytes()
        index_bytes = indices.astype(np.uint16).tobytes()

        self.buffer_data.extend(vertex_bytes)
        self.buffer_data.extend(index_bytes)

        total_bytes = len(vertex_bytes) + len(index_bytes)
        vertex_byte_length = len(vertex_bytes)
        index_byte_length = len(index_bytes)
        index_count = len(indices)

        return {
            "byte_offset": byte_offset,
            "total_bytes": total_bytes,
            "vertex_byte_length": vertex_byte_length,
            "index_byte_length": index_byte_length,
            "index_count": index_count,
            "vertex_count": len(vertices),
        }

    def export(self, building: Building3D, output_path: str) -> str:
        """Export a Building3D to a GLB file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.buffer_data = bytearray()

        nodes = []
        meshes = []
        accessors = []
        bufferViews = []

        for i, room in enumerate(building.rooms):
            mesh_info = self._build_room_mesh(room, i)

            # Buffer views
            pos_norm_view = len(bufferViews)
            bufferViews.append({
                "buffer": 0,
                "byteOffset": mesh_info["byte_offset"],
                "byteLength": mesh_info["vertex_byte_length"],
                "target": 34962,  # ARRAY_BUFFER
            })

            index_view = len(bufferViews)
            bufferViews.append({
                "buffer": 0,
                "byteOffset": mesh_info["byte_offset"] + mesh_info["vertex_byte_length"],
                "byteLength": mesh_info["index_byte_length"],
                "target": 34963,  # ELEMENT_ARRAY_BUFFER
            })

            # Position accessor (3 floats)
            pos_accessor = len(accessors)
            accessors.append({
                "bufferView": pos_norm_view,
                "byteOffset": 0,
                "componentType": 5126,  # FLOAT
                "count": mesh_info["vertex_count"],
                "type": "VEC3",
                "max": [room.x + room.width, room.y + room.depth, room.z + room.height],
                "min": [room.x, room.y, room.z],
            })

            # Normal accessor (3 floats, offset 12 bytes)
            norm_accessor = len(accessors)
            accessors.append({
                "bufferView": pos_norm_view,
                "byteOffset": 12,  # after position (3 floats = 12 bytes)
                "componentType": 5126,  # FLOAT
                "count": mesh_info["vertex_count"],
                "type": "VEC3",
                "max": [1, 1, 1],
                "min": [-1, -1, -1],
            })

            # Index accessor
            idx_accessor = len(accessors)
            accessors.append({
                "bufferView": index_view,
                "byteOffset": 0,
                "componentType": 5123,  # UNSIGNED_SHORT
                "count": mesh_info["index_count"],
                "type": "SCALAR",
                "max": [mesh_info["vertex_count"] - 1],
                "min": [0],
            })

            # Mesh primitive
            mesh = len(meshes)
            meshes.append({
                "primitives": [{
                    "attributes": {
                        "POSITION": pos_accessor,
                        "NORMAL": norm_accessor,
                    },
                    "indices": idx_accessor,
                    "mode": 4,  # TRIANGLES
                    "material": 0,
                }]
            })

            # Node
            node = len(nodes)
            nodes.append({
                "mesh": mesh,
                "name": f"{room.type}_{room.room_id}",
            })

        # Materials (single simple material for now)
        materials = [{
            "pbrMetallicRoughness": {
                "baseColorFactor": [0.8, 0.8, 0.8, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 0.8,
            },
            "doubleSided": True,
        }]

        # Scene
        scene = {
            "nodes": list(range(len(nodes))),
        }

        # Root JSON
        gltf = {
            "asset": {
                "version": "2.0",
                "generator": "Sketch2Build AI GLBExporter",
            },
            "scene": 0,
            "scenes": [scene],
            "nodes": nodes,
            "meshes": meshes,
            "accessors": accessors,
            "bufferViews": bufferViews,
            "buffers": [{
                "byteLength": len(self.buffer_data),
            }],
            "materials": materials,
        }

        json_data = json.dumps(gltf).encode("utf-8")
        json_data = self._pad_json(json_data)
        bin_data = self._pad_bin(self.buffer_data)

        # Calculate total length
        total_length = (
            12  # header
            + 8 + len(json_data)  # JSON chunk header + data
            + 8 + len(bin_data)   # BIN chunk header + data
        )

        # Build GLB file
        glb = bytearray()
        # Header
        glb.extend(self.GLTF_MAGIC)
        glb.extend(struct.pack("<I", self.GLTF_VERSION))
        glb.extend(struct.pack("<I", total_length))
        # JSON chunk
        glb.extend(struct.pack("<I", len(json_data)))
        glb.extend(struct.pack("<I", self.CHUNK_TYPE_JSON))
        glb.extend(json_data)
        # BIN chunk
        glb.extend(struct.pack("<I", len(bin_data)))
        glb.extend(struct.pack("<I", self.CHUNK_TYPE_BIN))
        glb.extend(bin_data)

        output_path.write_bytes(glb)

        logger.info(
            "GLB exported",
            path=str(output_path),
            rooms=len(building.rooms),
            size_bytes=len(glb),
        )
        return str(output_path)
