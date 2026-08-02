"""IFC (Industry Foundation Classes) export for BIM workflows.

Generates IFC-STEP format files from 3D building geometry that can be
imported into Revit, ArchiCAD, Tekla, and other BIM tools.

Uses a lightweight IFC writer (no ifcopenshell dependency)."""

import structlog
from datetime import datetime
from typing import Any
from pathlib import Path
import uuid

from src.models.massing.extruder import Building3D, Room3D, Wall3D

logger = structlog.get_logger()


class IFCExporter:
    """Export building geometry to IFC format."""

    IFC_SCHEMA = "IFC4"
    HEADER_TEMPLATE = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION(('ViewDefinition [CoordinationView_V2.0]'),'2;1');
FILE_NAME('{filename}','{timestamp}',('{author}'),('{organization}'),'Sketch2Build AI','Sketch2Build AI','');
FILE_SCHEMA(('{schema}'));
ENDSEC;
"""

    def __init__(self, project_name: str = "Sketch2Build_Project", author: str = "Sketch2Build AI"):
        self.project_name = project_name
        self.author = author
        self.entity_counter = 1000

    def _next_id(self) -> int:
        self.entity_counter += 1
        return self.entity_counter

    def _guid(self) -> str:
        return "0" + str(uuid.uuid4()).replace("-", "")[:21].upper()

    def _build_cartesian_point(self, entity_id: int, x: float, y: float, z: float = 0.0) -> str:
        return f"#{entity_id}=IFCCARTESIANPOINT(({x:.6f},{y:.6f},{z:.6f}));"

    def _build_direction(self, entity_id: int, x: float, y: float, z: float = 0.0) -> str:
        return f"#{entity_id}=IFCDIRECTION(({x:.6f},{y:.6f},{z:.6f}));"

    def _build_axis2placement3d(self, entity_id: int, location_id: int, axis_id: int, ref_id: int) -> str:
        return f"#{entity_id}=IFCAXIS2PLACEMENT3D(#{location_id},#{axis_id},#{ref_id});"

    def _build_local_placement(self, entity_id: int, relative_placement_id: int, parent_id: int | None = None) -> str:
        if parent_id:
            return f"#{entity_id}=IFCLOCALPLACEMENT(#{parent_id},#{relative_placement_id});"
        return f"#{entity_id}=IFCLOCALPLACEMENT($,#{relative_placement_id});"

    def _build_solid_brep(self, entity_id: int, shell_id: int) -> str:
        return f"#{entity_id}=IFCFACETEDBREP(#{shell_id});"

    def _build_closed_shell(self, entity_id: int, face_ids: list[int]) -> str:
        faces_str = ",".join(f"#{fid}" for fid in face_ids)
        return f"#{entity_id}=IFCCLOSEDSHELL(({faces_str}));"

    def _build_face(self, entity_id: int, bound_id: int) -> str:
        return f"#{entity_id}=IFCFACE((#{bound_id}));"

    def _build_face_bound(self, entity_id: int, loop_id: int, orientation: str = ".T.") -> str:
        return f"#{entity_id}=IFCFACEBOUND(#{loop_id},{orientation});"

    def _build_poly_loop(self, entity_id: int, point_ids: list[int]) -> str:
        points_str = ",".join(f"#{pid}" for pid in point_ids)
        return f"#{entity_id}=IFCPOLYLOOP(({points_str}));"

    def _build_shape_representation(self, entity_id: int, context_id: int, rep_type: str, item_ids: list[int]) -> str:
        items_str = ",".join(f"#{iid}" for iid in item_ids)
        return f"#{entity_id}=IFCSHAPEREPRESENTATION(#{context_id},'{rep_type}','Brep',({items_str}));"

    def _build_product_definition_shape(self, entity_id: int, rep_ids: list[int]) -> str:
        reps_str = ",".join(f"#{rid}" for rid in rep_ids)
        return f"#{entity_id}=IFCPRODUCTDEFINITIONSHAPE($,$,({reps_str}));"

    def _build_wall(self, entity_id: int, guid: str, name: str, placement_id: int, shape_id: int) -> str:
        return f"#{entity_id}=IFCWALL(''{guid}'',#20,'{name}','AI-generated wall',$,#{placement_id},#{shape_id},$);"

    def _build_space(self, entity_id: int, guid: str, name: str, placement_id: int, shape_id: int) -> str:
        return f"#{entity_id}=IFCSPACE(''{guid}'',#20,'{name}','AI-generated space',$,#{placement_id},#{shape_id},$,.INTERNAL.,$);"

    def _build_building(self, entity_id: int, guid: str, name: str, placement_id: int) -> str:
        return f"#{entity_id}=IFCBUILDING(''{guid}'',#20,'{name}','',$,#{placement_id},$,$,$,$,$,$);"

    def _build_site(self, entity_id: int, guid: str, name: str, placement_id: int) -> str:
        return f"#{entity_id}=IFCSITE(''{guid}'',#20,'{name}','',$,#{placement_id},$,$,$,$,$,$,$);"

    def _build_project(self, entity_id: int, guid: str, name: str, context_id: int) -> str:
        return f"#{entity_id}=IFCPROJECT(''{guid}'',#20,'{name}','',$,$,$,({context_id}),$);"

    def _build_rel_aggregates(self, entity_id: int, guid: str, rel_id: int, related_ids: list[int]) -> str:
        related_str = ",".join(f"#{rid}" for rid in related_ids)
        return f"#{entity_id}=IFCRELAGGREGATES(''{guid}'',#20,$,$,#{rel_id},({related_str}));"

    def _build_rel_contained(self, entity_id: int, guid: str, rel_id: int, related_ids: list[int]) -> str:
        related_str = ",".join(f"#{rid}" for rid in related_ids)
        return f"#{entity_id}=IFCRELCONTAINEDINSPATIALSTRUCTURE(''{guid}'',#20,$,$,({related_str}),#{rel_id});"

    def _build_geom_context(self, entity_id: int, coord_dim: int = 3) -> str:
        return f"#{entity_id}=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.0E-05,#{(entity_id+1)},#{(entity_id+2)});"

    def _build_entity(self, name: str, entity_id: int, *args) -> str:
        """Build a generic IFC entity line."""
        args_str = ",".join(str(a) for a in args)
        return f"#{entity_id}=IFC{name.upper()}({args_str});"

    def export(self, building: Building3D, output_path: str) -> str:
        """Export a Building3D to an IFC file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        header = self.HEADER_TEMPLATE.format(
            filename=output_path.name,
            timestamp=timestamp,
            author=self.author,
            organization="Sketch2Build",
            schema=self.IFC_SCHEMA,
        )

        lines = [header, "DATA;"]

        # Owner history
        lines.append(f"#20=IFCOWNERHISTORY(#21,#22,$,.ADDED.,$,$,$,{int(datetime.now().timestamp())});")
        lines.append(f"#21=IFCPERSONANDORGANIZATION(#22,#23,$);")
        lines.append(f"#22=IFCPERSON($,$,'{self.author}',$,$,$,$,$);")
        lines.append(f"#23=IFCORGANIZATION($,'Sketch2Build',$,$,$);")

        # Geometric context
        ctx_id = self._next_id()
        ctx_id = 30  # Fixed context id
        lines.append(self._build_geom_context(ctx_id))
        lines.append(self._build_cartesian_point(ctx_id + 1, 0, 0, 0))  # origin
        lines.append(self._build_direction(ctx_id + 2, 0, 0, 1))         # Z-axis
        lines.append(self._build_direction(ctx_id + 3, 1, 0, 0))         # X-axis
        lines.append(self._build_axis2placement3d(ctx_id + 4, ctx_id + 1, ctx_id + 2, ctx_id + 3))
        lines.append(self._build_local_placement(ctx_id + 5, ctx_id + 4))

        # Project
        project_id = self._next_id()
        project_id = ctx_id + 6
        lines.append(self._build_project(project_id, self._guid(), self.project_name, ctx_id))

        # Site
        site_id = self._next_id()
        site_placement = self._next_id()
        lines.append(self._build_local_placement(site_placement, ctx_id + 4))
        lines.append(self._build_site(site_id, self._guid(), "Site", site_placement))
        lines.append(self._build_rel_aggregates(self._next_id(), self._guid(), project_id, [site_id]))

        # Building
        building_id = self._next_id()
        building_placement = self._next_id()
        lines.append(self._build_local_placement(building_placement, ctx_id + 4, site_placement))
        lines.append(self._build_building(building_id, self._guid(), "Building", building_placement))
        lines.append(self._build_rel_aggregates(self._next_id(), self._guid(), site_id, [building_id]))

        # Export each room as a space with its geometry
        room_entities = []
        for room in building.rooms:
            room_entities.extend(self._export_room(lines, room, building_id, ctx_id))

        # RelContainedInSpatialStructure for all rooms
        if room_entities:
            rel_id = self._next_id()
            lines.append(self._build_rel_contained(rel_id, self._guid(), building_id, room_entities))

        lines.append("ENDSEC;")
        lines.append("END-ISO-10303-21;")

        ifc_content = "\n".join(lines)
        output_path.write_text(ifc_content, encoding="utf-8")

        logger.info("IFC export complete", path=str(output_path), rooms=len(building.rooms))
        return str(output_path)

    def _export_room(
        self,
        lines: list[str],
        room: Room3D,
        building_id: int,
        context_id: int,
    ) -> list[int]:
        """Export a room's geometry and return the entity IDs."""
        # Room placement (at room origin)
        origin_id = self._next_id()
        lines.append(self._build_cartesian_point(origin_id, room.x, room.y, room.z))
        z_axis_id = self._next_id()
        lines.append(self._build_direction(z_axis_id, 0, 0, 1))
        x_axis_id = self._next_id()
        lines.append(self._build_direction(x_axis_id, 1, 0, 0))
        placement3d_id = self._next_id()
        lines.append(self._build_axis2placement3d(placement3d_id, origin_id, z_axis_id, x_axis_id))
        local_placement_id = self._next_id()
        lines.append(self._build_local_placement(local_placement_id, placement3d_id))

        # Build geometry: a simple box for the room volume
        # Define 8 vertices of the room box
        w, d, h = room.width, room.depth, room.height
        vertices = [
            (0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0),  # bottom
            (0, 0, h), (w, 0, h), (w, d, h), (0, d, h),  # top
        ]

        vertex_ids = []
        for v in vertices:
            vid = self._next_id()
            lines.append(self._build_cartesian_point(vid, v[0], v[1], v[2]))
            vertex_ids.append(vid)

        # 6 faces (each face is a polygon loop)
        # Bottom face: 0-3
        bottom_loop_id = self._next_id()
        lines.append(self._build_poly_loop(bottom_loop_id, vertex_ids[:4]))
        bottom_bound_id = self._next_id()
        lines.append(self._build_face_bound(bottom_bound_id, bottom_loop_id))
        bottom_face_id = self._next_id()
        lines.append(self._build_face(bottom_face_id, bottom_bound_id))

        # Top face: 4-7
        top_loop_id = self._next_id()
        lines.append(self._build_poly_loop(top_loop_id, vertex_ids[4:8]))
        top_bound_id = self._next_id()
        lines.append(self._build_face_bound(top_bound_id, top_loop_id))
        top_face_id = self._next_id()
        lines.append(self._build_face(top_face_id, top_bound_id))

        # Side faces (4 walls)
        side_face_ids = [bottom_face_id, top_face_id]
        side_loops = [
            [0, 1, 5, 4],  # front
            [1, 2, 6, 5],  # right
            [2, 3, 7, 6],  # back
            [3, 0, 4, 7],  # left
        ]
        for loop in side_loops:
            loop_id = self._next_id()
            lines.append(self._build_poly_loop(loop_id, [vertex_ids[i] for i in loop]))
            bound_id = self._next_id()
            lines.append(self._build_face_bound(bound_id, loop_id))
            face_id = self._next_id()
            lines.append(self._build_face(face_id, bound_id))
            side_face_ids.append(face_id)

        # Closed shell
        shell_id = self._next_id()
        lines.append(self._build_closed_shell(shell_id, side_face_ids))

        # Faceted BRep
        brep_id = self._next_id()
        lines.append(self._build_solid_brep(brep_id, shell_id))

        # Shape representation
        shape_rep_id = self._next_id()
        lines.append(self._build_shape_representation(shape_rep_id, context_id, "Body", [brep_id]))

        # Product definition shape
        product_shape_id = self._next_id()
        lines.append(self._build_product_definition_shape(product_shape_id, [shape_rep_id]))

        # Space entity
        space_id = self._next_id()
        lines.append(self._build_space(
            space_id, self._guid(), f"{room.type}_{room.room_id}",
            local_placement_id, product_shape_id,
        ))

        return [space_id]
