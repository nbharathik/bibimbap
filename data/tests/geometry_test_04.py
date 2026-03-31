"""
Geometry Test 04 - CREATE: Room Left of Column
================================================

Prompt:
    "Insert a room (IfcSpace) to the area that is left of the column
    with GlobalId = '3A5GfH23DBvBYpavCfWh4z'."

IFC file: 01/01/01_01_004.ifc
Category: Geometry / Create

What this test evaluates:
    The LLM must create exactly one new IfcSpace positioned to the left
    (-X direction) of the referenced column, within the area bounded by
    the existing walls. "Left" is interpreted as negative X direction.

Metrics:
    object_exists (bool):
        True if exactly one new IfcSpace was created.

    right_dimensions (bool):
        True if the space footprint roughly matches the gap defined by the
        walls (~6m x 6m). The expected x_max is ~6.35m (left half only).

    right_location (bool):
        True if the space is located left of the column (within the wall
        boundary). Accepts both the left-half (~6.35m) and full-footprint
        (~12.75m) interpretations of "left".

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + spatial containment + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, within_abs,
    compute_integrity, check_is_correct_type,
    check_spatial_containment, check_elements_preserved,
)


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Insert a room (IfcSpace) to the area that is left of the column with GlobalId = '3A5GfH23DBvBYpavCfWh4z'."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    TOL = 0.5
    # expected space boundaries based on the wall geometry
    TGT_X_MIN = 0.20
    TGT_Y_MIN, TGT_Y_MAX = 0.20, 6.70
    TGT_Z_MIN, TGT_Z_MAX = 0.0, 3.0

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    new_spaces = find_new_elements(ifc_original, ifc_edited, "IfcSpace")
    if not new_spaces:
        return metrics

    metrics["object_exists"] = True

    if len(new_spaces) != 1:
        return metrics

    space = new_spaces[0]
    try:
        space_bbox = get_bbox(space)
    except RuntimeError:
        return metrics

    # check common boundary matches
    common_match = (
        within_abs(space_bbox["x_min"], TGT_X_MIN, TOL)
        and within_abs(space_bbox["y_min"], TGT_Y_MIN, TOL)
        and within_abs(space_bbox["y_max"], TGT_Y_MAX, TOL)
        and within_abs(space_bbox["z_min"], TGT_Z_MIN, TOL)
        and within_abs(space_bbox["z_max"], TGT_Z_MAX, TOL)
    )

    left_of_column = False
    footprint_matches = False

    if common_match:
        # left half only (~6.35m x_max) - correct answer
        if within_abs(space_bbox["x_max"], 6.35, TOL):
            left_of_column = True
            footprint_matches = True
        # full footprint (~12.75m x_max) - acceptable location but wrong dimensions
        elif within_abs(space_bbox["x_max"], 12.75, TOL):
            left_of_column = True
            footprint_matches = False

    if left_of_column:
        metrics["right_location"] = True
    if footprint_matches:
        metrics["right_dimensions"] = True

    # integrity
    sub_checks = [
        check_is_correct_type(space, "IfcSpace"),
        check_spatial_containment(ifc_edited, space),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
