"""
Test 04 - Basic CREATE: Column at Position
============================================

Prompt:
    "Insert a column with the height of 3m in (12, 8)."

IFC file: basic_tasks.ifc
Category: Basic / Create

What this test evaluates:
    The LLM must create exactly one new IfcColumn with a height of 3m and place
    it at the specified coordinates. Since the prompt "(12, 8)" is ambiguous
    (could be x=12,y=8 or x=8,y=12), both interpretations are accepted.
    No cross-section dimensions are specified, so any reasonable size is fine.

Metrics:
    object_exists (bool):
        True if exactly one new IfcColumn was created. If zero or more than one
        new column is found, the test returns early with only this metric set.

    right_dimensions (bool):
        True if the column height is 3m. Tolerance: ±0.05m.
        Width and depth are not checked (not specified in prompt).

    right_location (bool):
        True if the point (12, 8) OR (8, 12) falls within the column's XY
        footprint. Tolerance: ±0.5m on each side.

    integrity_constraint (float, 0.0–1.0):
        Average of the following sub-checks (each 0.0 or 1.0):
        1. Correct IFC type - element is IfcColumn
        2. Spatial containment - column is assigned to a storey
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
    """Prompt: Insert a column with the height of 3m in (12, 8)."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    EXPECTED_HEIGHT = 3.0
    # Accept both (x=12,y=8) and (x=8,y=12) since prompt is ambiguous
    POSITIONS = [(12.0, 8.0), (8.0, 12.0)]
    DIM_TOL = 0.05
    LOC_TOL = 0.5

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # find new columns - must be exactly one
    new_columns = find_new_elements(ifc_original, ifc_edited, "IfcColumn")
    if not new_columns:
        return metrics

    metrics["object_exists"] = True

    if len(new_columns) != 1:
        return metrics

    column = new_columns[0]

    try:
        bbox = get_bbox(column)
    except RuntimeError:
        return metrics

    shape_dims = get_shape_dims(column)
    if shape_dims is None:
        return metrics
    width, depth, height = shape_dims

    # right_dimensions: height ~3m
    if within_abs(height, EXPECTED_HEIGHT, DIM_TOL):
        metrics["right_dimensions"] = True

    # right_location: column footprint contains (12,8) or (8,12)
    for px, py in POSITIONS:
        if point_in_bbox_xy(px, py, bbox, tol=LOC_TOL):
            metrics["right_location"] = True
            break

    # integrity: average of sub-checks
    sub_checks = [
        check_is_correct_type(column, "IfcColumn"),
        check_spatial_containment(ifc_edited, column),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
