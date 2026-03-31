"""
Topological Test 03 - CREATE: Wall Separating Two Rooms
========================================================

Prompt:
    "Insert a wall that separates the rooms with the ids
    0rMMWWDi1E0Qbe7dlPjRaK, 0rMMWWDi1E0Qbe7dlPjRcx."

IFC file: 01/02/01_02_003.ifc
Category: Topological / Create

What this test evaluates:
    The LLM must create exactly one new IfcWall positioned between the two
    referenced rooms. The wall center should lie on the line between the
    room centers (triangle inequality check).

Metrics:
    object_exists (bool):
        True if exactly one new IfcWall was created.

    right_dimensions (bool):
        True if the wall has reasonable height (>1.5m) and length (>0.5m).

    right_location (bool):
        True if the wall is positioned between the two rooms (sum of distances
        from wall to each room center equals distance between room centers, ±1m).

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + spatial containment + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, get_shape_dims, within_abs,
    compute_integrity, check_is_correct_type,
    check_spatial_containment, check_elements_preserved,
)


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Insert a wall that separates the rooms with the ids 0rMMWWDi1E0Qbe7dlPjRaK, 0rMMWWDi1E0Qbe7dlPjRcx."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    ROOM_IDS = ["0rMMWWDi1E0Qbe7dlPjRaK", "0rMMWWDi1E0Qbe7dlPjRcx"]
    LOC_TOL = 1.0

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

    wall_center_x = wall_bbox["x_c"]
    wall_center_y = wall_bbox["y_c"]

    # get room geometry
    room_centers = []
    for room_id in ROOM_IDS:
        try:
            room = ifc_edited.by_guid(room_id)
            room_bbox = get_bbox(room)
            room_centers.append((room_bbox["x_c"], room_bbox["y_c"]))
        except RuntimeError:
            continue

    if len(room_centers) >= 2:
        r1x, r1y = room_centers[0]
        r2x, r2y = room_centers[1]

        dist_r1_wall = ((wall_center_x - r1x)**2 + (wall_center_y - r1y)**2)**0.5
        dist_r2_wall = ((wall_center_x - r2x)**2 + (wall_center_y - r2y)**2)**0.5
        dist_r1_r2 = ((r1x - r2x)**2 + (r1y - r2y)**2)**0.5

        # wall between rooms: d(r1,wall) + d(r2,wall) ≈ d(r1,r2)
        if abs((dist_r1_wall + dist_r2_wall) - dist_r1_r2) < LOC_TOL:
            metrics["right_location"] = True

    # right_dimensions: reasonable wall
    wall_length = max(width_wall, thickness_wall)
    if height_wall > 1.5 and wall_length > 0.5:
        metrics["right_dimensions"] = True

    # integrity
    sub_checks = [
        check_is_correct_type(wall, "IfcWall"),
        check_spatial_containment(ifc_edited, wall),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
