"""
Test 05 - Basic CREATE: Wall at Starting Point
================================================

Prompt:
    "Add a wall with a length of 15m beginning in (0, -10)."

IFC file: basic_tasks.ifc
Category: Basic / Create

What this test evaluates:
    The LLM must create exactly one new IfcWall with a length of 15m that
    starts at or passes through the point (0, -10). The prompt does not specify
    direction, height, or thickness, so the wall can extend in any direction
    and have any reasonable height/thickness.

Metrics:
    object_exists (bool):
        True if exactly one new IfcWall was created. If zero or more than one
        new wall is found, the test returns early with only this metric set.

    right_dimensions (bool):
        True if the wall's longest horizontal dimension is 15m. Tolerance: ±0.05m.
        Height and thickness are not checked (not specified in prompt).

    right_location (bool):
        True if the starting point (0, -10) is near the wall. This is checked
        two ways (either passes):
        1. The point falls within the wall's XY footprint (±0.5m tolerance)
        2. A wall edge/corner is near the point - i.e., one X-edge is near
           x=0 AND one Y-edge is near y=-10 (±0.5m tolerance each)

    integrity_constraint (float, 0.0–1.0):
        Average of the following sub-checks (each 0.0 or 1.0):
        1. Correct IFC type - element is IfcWall
        2. Spatial containment - wall is assigned to a storey
        3. Elements preserved - all original GUIDs still exist
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, get_shape_dims, within_abs,
    point_in_bbox_xy, compute_integrity, check_is_correct_type,
    check_spatial_containment,
    check_elements_preserved,
)


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add a wall with a length of 15m beginning in (0, -10)."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    EXPECTED_LENGTH = 15.0
    START_X, START_Y = 0.0, -10.0
    DIM_TOL = 0.05
    LOC_TOL = 0.5

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # find new walls - must be exactly one
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

    shape_dims = get_shape_dims(wall)
    if shape_dims is None:
        return metrics
    width, depth, height = shape_dims

    # right_dimensions: longest horizontal dimension ~15m
    # Wall can be in any direction, so check both x and y extents
    wall_length = max(width, depth)
    if within_abs(wall_length, EXPECTED_LENGTH, DIM_TOL):
        metrics["right_dimensions"] = True

    # right_location: the starting point (0, -10) should be at or near
    # one edge of the wall. Check if the point falls within the wall's
    # footprint, or if a wall edge/corner is near the starting point.
    at_start = point_in_bbox_xy(START_X, START_Y, bbox, tol=LOC_TOL)

    edge_near_x = (within_abs(bbox["x_min"], START_X, LOC_TOL) or
                    within_abs(bbox["x_max"], START_X, LOC_TOL))
    edge_near_y = (within_abs(bbox["y_min"], START_Y, LOC_TOL) or
                    within_abs(bbox["y_max"], START_Y, LOC_TOL))

    if at_start or (edge_near_x and edge_near_y):
        metrics["right_location"] = True

    # integrity: average of sub-checks
    sub_checks = [
        check_is_correct_type(wall, "IfcWall"),
        check_spatial_containment(ifc_edited, wall),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
