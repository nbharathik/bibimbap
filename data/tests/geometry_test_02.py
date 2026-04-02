"""
Geometry Test 02 - CREATE: Column at Centroid of Walls
=======================================================

Prompt:
    "Create a column in the centroid of the four walls in this IFC file."

IFC file: 01/01/01_01_002.ifc
Category: Geometry / Create

What this test evaluates:
    The LLM must create exactly one new IfcColumn placed at the centroid
    (geometric center) of the 4 existing walls. The centroid is computed as
    the average of wall bounding-box centers OR the center of the enclosing
    bounding box of all walls — both interpretations are accepted.

Metrics:
    object_exists (bool):
        True if exactly one new IfcColumn was created.

    right_dimensions (bool):
        True if the column has reasonable dimensions (height > 1m, width/depth
        between 0.1m and 2.0m). No specific dimensions are given in the prompt.

    right_location (bool):
        True if the column center is at the centroid of the walls (±0.5m).
        Both average-of-centers and bounding-box-center are accepted.

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + spatial containment + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, within_abs,
    compute_integrity,    check_spatial_containment, check_elements_preserved,
)
from .utils.clash_utils import check_clash_integrity


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a column in the centroid of the four walls in this IFC file."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    LOC_TOL = 0.5

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    new_columns = find_new_elements(ifc_original, ifc_edited, "IfcColumn")
    if not new_columns:
        return metrics

    metrics["object_exists"] = True

    if len(new_columns) != 1:
        return metrics

    column = new_columns[0]
    try:
        col_bbox = get_bbox(column)
    except RuntimeError:
        return metrics

    # right_dimensions: reasonable column size (no specific dims in prompt)
    col_width = col_bbox["x_len"]
    col_depth = col_bbox["y_len"]
    col_height = col_bbox["z_len"]
    if 0.1 <= col_width <= 2.0 and 0.1 <= col_depth <= 2.0 and col_height > 1.0:
        metrics["right_dimensions"] = True

    # get wall bounding boxes to compute centroid
    walls = ifc_edited.by_type("IfcWall")
    if len(walls) < 4:
        sub_checks = [
            check_spatial_containment(ifc_edited, column),
            check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[column.GlobalId], clash_mode="collision"),
            check_elements_preserved(ifc_original, ifc_edited),
        ]
        metrics["integrity_constraint"] = compute_integrity(sub_checks)
        return metrics

    wall_bboxes = []
    for wall in walls:
        try:
            wall_bboxes.append(get_bbox(wall))
        except RuntimeError:
            continue

    if len(wall_bboxes) < 4:
        sub_checks = [
            check_spatial_containment(ifc_edited, column),
            check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[column.GlobalId], clash_mode="collision"),
            check_elements_preserved(ifc_original, ifc_edited),
        ]
        metrics["integrity_constraint"] = compute_integrity(sub_checks)
        return metrics

    # centroid interpretation 1: average of wall centers
    avg_x_c = sum(b["x_c"] for b in wall_bboxes) / len(wall_bboxes)
    avg_y_c = sum(b["y_c"] for b in wall_bboxes) / len(wall_bboxes)

    # centroid interpretation 2: center of enclosing bounding box
    box_x_c = (min(b["x_min"] for b in wall_bboxes) + max(b["x_max"] for b in wall_bboxes)) / 2.0
    box_y_c = (min(b["y_min"] for b in wall_bboxes) + max(b["y_max"] for b in wall_bboxes)) / 2.0

    at_centroid_avg = within_abs(col_bbox["x_c"], avg_x_c, LOC_TOL) and within_abs(col_bbox["y_c"], avg_y_c, LOC_TOL)
    at_centroid_box = within_abs(col_bbox["x_c"], box_x_c, LOC_TOL) and within_abs(col_bbox["y_c"], box_y_c, LOC_TOL)

    if at_centroid_avg or at_centroid_box:
        metrics["right_location"] = True

    # integrity
    sub_checks = [
        check_spatial_containment(ifc_edited, column),
        check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[column.GlobalId], clash_mode="collision"),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
