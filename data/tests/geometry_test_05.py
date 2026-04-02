"""
Geometry Test 05 - CREATE: Wall with Direction
================================================

Prompt:
    "Create a wall with a length of 5m starting at point (10, 5)
    pointing to direction (1, 0)."

IFC file: empty.ifc
Category: Geometry / Create

What this test evaluates:
    The LLM must create exactly one new IfcWall with a length of 5m,
    starting at (10, 5), extending in the +X direction (1, 0). Since the
    direction is (1, 0), the wall should extend from x=10 to x=15 at y=5.

Metrics:
    object_exists (bool):
        True if exactly one new IfcWall was created.

    right_dimensions (bool):
        True if the wall's length along the X-axis is ~5m. Tolerance: ±0.5m.

    right_location (bool):
        True if the wall starts near (10, 5). Tolerance: ±0.5m.

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + spatial containment + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, within_abs, point_in_bbox_xy,
    compute_integrity,    check_spatial_containment, check_elements_preserved,
)
from .utils.clash_utils import check_clash_integrity


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a wall with a length of 5m starting at point (10, 5) pointing to direction (1, 0)."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    EXPECTED_LENGTH = 5.0
    START_X, START_Y = 10.0, 5.0
    DIM_TOL = 0.5
    LOC_TOL = 0.5

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
        bbox = get_bbox(wall)
    except RuntimeError:
        return metrics

    # right_dimensions: wall length ~5m
    # direction is (1,0) so length should be along X-axis
    x_len = bbox["x_len"]
    y_len = bbox["y_len"]
    wall_length = max(x_len, y_len)
    if within_abs(wall_length, EXPECTED_LENGTH, DIM_TOL):
        metrics["right_dimensions"] = True

    # right_location: starting point (10, 5) near a wall edge
    match_start_x = within_abs(bbox["x_min"], START_X, LOC_TOL)
    match_start_y = (within_abs(bbox["y_min"], START_Y, LOC_TOL) or
                     within_abs(bbox["y_max"], START_Y, LOC_TOL) or
                     within_abs(bbox["y_c"], START_Y, LOC_TOL))

    if match_start_x and match_start_y:
        metrics["right_location"] = True

    # integrity
    sub_checks = [
        check_spatial_containment(ifc_edited, wall),
        check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[wall.GlobalId], clash_mode="collision"),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
