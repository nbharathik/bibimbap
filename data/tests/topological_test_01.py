"""
Topological Test 01 - CREATE: Wall to Enclose Room
====================================================

Prompt:
    "Add a wall to the room with the id 3_DHXxtdb3wRKlXgyMiH4s
    so that it gets fully enclosed."

IFC file: 01/02/01_02_001.ifc
Category: Topological / Create

What this test evaluates:
    The LLM must create exactly one new IfcWall that closes an open side of
    the referenced room (IfcSpace). The wall must be at a room boundary and
    its length must match the room opening dimension.

Metrics:
    object_exists (bool):
        True if exactly one new IfcWall was created.

    right_dimensions (bool):
        True if the wall length matches one of the room dimensions (±0.5m).

    right_location (bool):
        True if the wall is at one of the room boundaries (±0.5m).

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + spatial containment + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, get_shape_dims, within_abs,
    compute_integrity,    check_spatial_containment, check_elements_preserved,
)
from .utils.clash_utils import check_clash_integrity


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add a wall to the room with the id 3_DHXxtdb3wRKlXgyMiH4s so that it gets fully enclosed."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    ROOM_GUID = "3_DHXxtdb3wRKlXgyMiH4s"
    TOL = 0.5

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    new_walls = find_new_elements(ifc_original, ifc_edited, "IfcWall")
    if not new_walls:
        return metrics

    metrics["object_exists"] = True

    if len(new_walls) != 1:
        return metrics

    wall = new_walls[0]
    try:
        wall_bbox = get_bbox(wall)
    except RuntimeError:
        return metrics

    wall_dims = get_shape_dims(wall)
    if wall_dims is None:
        return metrics
    width_wall, thickness_wall, height_wall = wall_dims

    # get room geometry
    try:
        room = ifc_edited.by_guid(ROOM_GUID)
        room_bbox = get_bbox(room)
        room_dims = get_shape_dims(room)
    except RuntimeError:
        sub_checks = [
            check_spatial_containment(ifc_edited, wall),
            check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[wall.GlobalId], clash_mode="collision"),
            check_elements_preserved(ifc_original, ifc_edited),
        ]
        metrics["integrity_constraint"] = compute_integrity(sub_checks)
        return metrics

    width_room, depth_room, height_room = room_dims

    # right_location: wall at a room boundary
    at_boundary = (
        within_abs(wall_bbox["x_min"], room_bbox["x_min"], TOL) or
        within_abs(wall_bbox["x_max"], room_bbox["x_max"], TOL) or
        within_abs(wall_bbox["y_min"], room_bbox["y_min"], TOL) or
        within_abs(wall_bbox["y_max"], room_bbox["y_max"], TOL)
    )
    if at_boundary:
        metrics["right_location"] = True

    # right_dimensions: wall length matches a room dimension
    wall_length = max(width_wall, thickness_wall)
    if (within_abs(wall_length, width_room, TOL) or
            within_abs(wall_length, depth_room, TOL)):
        metrics["right_dimensions"] = True

    # integrity
    sub_checks = [
        check_spatial_containment(ifc_edited, wall),
        check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[wall.GlobalId], clash_mode="collision"),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
