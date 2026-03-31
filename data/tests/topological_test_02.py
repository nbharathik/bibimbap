"""
Topological Test 02 - CREATE: Column in Inner Space of Walls
=============================================================

Prompt:
    "Insert a column to the inner space of the walls with ids
    3_DHXxtdb3wRKlXgyMiHOP, 3_DHXxtdb3wRKlXgyMiHR$,
    3_DHXxtdb3wRKlXgyMiH5o, 1IMYx2Ej12vu3iYKHoTn08."

IFC file: 01/02/01_02_002.ifc
Category: Topological / Create

What this test evaluates:
    The LLM must create exactly one new IfcColumn placed inside the area
    enclosed by the 4 referenced walls.

Metrics:
    object_exists (bool):
        True if exactly one new IfcColumn was created.

    right_dimensions (bool):
        True if the column has reasonable dimensions (width/depth 0.1-2.0m,
        height > 1.0m). No specific dimensions are given in the prompt.

    right_location (bool):
        True if the column center is within the bounding box of the 4 walls (±0.5m).

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + spatial containment + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, point_in_bbox_xy,
    compute_integrity, check_is_correct_type,
    check_spatial_containment, check_elements_preserved,
)


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Insert a column to the inner space of the walls with ids [3_DHXxtdb3wRKlXgyMiHOP, 3_DHXxtdb3wRKlXgyMiHR$, 3_DHXxtdb3wRKlXgyMiH5o, 1IMYx2Ej12vu3iYKHoTn08]."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    WALL_IDS = ["3_DHXxtdb3wRKlXgyMiHOP", "3_DHXxtdb3wRKlXgyMiHR$",
                "3_DHXxtdb3wRKlXgyMiH5o", "1IMYx2Ej12vu3iYKHoTn08"]
    TOL = 0.5

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

    # right_dimensions: reasonable column size
    if (0.1 <= col_bbox["x_len"] <= 2.0 and
        0.1 <= col_bbox["y_len"] <= 2.0 and
        col_bbox["z_len"] > 1.0):
        metrics["right_dimensions"] = True

    # get wall bounding boxes to determine inner space
    wall_bboxes = []
    for wall_id in WALL_IDS:
        try:
            wall = ifc_edited.by_guid(wall_id)
            wall_bboxes.append(get_bbox(wall))
        except RuntimeError:
            continue

    if len(wall_bboxes) >= 4:
        # inner space bounding box
        space_bbox = {
            "x_min": min(wb["x_min"] for wb in wall_bboxes),
            "x_max": max(wb["x_max"] for wb in wall_bboxes),
            "y_min": min(wb["y_min"] for wb in wall_bboxes),
            "y_max": max(wb["y_max"] for wb in wall_bboxes),
        }

        if point_in_bbox_xy(col_bbox["x_c"], col_bbox["y_c"], space_bbox, tol=TOL):
            metrics["right_location"] = True

    # integrity
    sub_checks = [
        check_is_correct_type(column, "IfcColumn"),
        check_spatial_containment(ifc_edited, column),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
