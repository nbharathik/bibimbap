"""
Test 02 - Basic CREATE: Slab with Dimensions and Position
==========================================================

Prompt:
    "Create a slab with dimensions of 10 by 5 meters and the width of
    20 centimeters with its bottom and center in (-30, 0)."

IFC file: basic_tasks.ifc
Category: Basic / Create

What this test evaluates:
    The LLM must create exactly one new IfcSlab with specified plan dimensions
    (10m × 5m), a thickness of 0.2m (the prompt says "width" but means slab
    thickness), and position it so its center is at x=-30, y=0 near the ground.

Metrics:
    object_exists (bool):
        True if exactly one new IfcSlab was created. If zero or more than one
        new slab is found, the test returns early with only this metric set.

    right_dimensions (bool):
        True if the slab plan dimensions are 10m × 5m (either orientation
        accepted) AND thickness is 0.2m. Tolerance: ±0.05m.

    right_location (bool):
        True if the slab center (x_c, y_c) is at (-30, 0) within ±0.5m,
        AND the slab z-center is within ±1.0m of z=0. The z-check is
        intentionally loose because "bottom" is ambiguous - any slab placed
        roughly at ground level is accepted.

    integrity_constraint (float, 0.0–1.0):
        Average of the following sub-checks (each 0.0 or 1.0):
        1. Correct IFC type - element is IfcSlab
        2. Spatial containment - slab is assigned to a storey
        3. Elements preserved - all original GUIDs still exist
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, get_shape_dims, within_abs, dims_match,
    compute_integrity, check_is_correct_type, check_spatial_containment,
    check_elements_preserved,
)


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a slab with dimensions of 10 by 5 meters and the width of 20 centimeters with its bottom and center in (-30, 0)."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    EXPECTED_PLAN = (10.0, 5.0)   # accept both orientations
    EXPECTED_THICKNESS = 0.2
    CENTER_X, CENTER_Y = -30.0, 0.0
    DIM_TOL = 0.05
    LOC_TOL = 0.5
    Z_CENTER_TOL = 1.0  # loose check for "bottom" - z_center within [-1, +1]

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    new_slabs = find_new_elements(ifc_original, ifc_edited, "IfcSlab")
    if not new_slabs:
        return metrics

    metrics["object_exists"] = True

    if len(new_slabs) != 1:
        return metrics

    slab = new_slabs[0]

    try:
        bbox = get_bbox(slab)
    except RuntimeError:
        return metrics

    shape_dims = get_shape_dims(slab)
    if shape_dims is None:
        return metrics
    width, depth, height = shape_dims

    # right_dimensions: plan dims match (10x5 or 5x10) AND thickness ~0.2m
    plan_ok = dims_match((width, depth), EXPECTED_PLAN, DIM_TOL)
    thickness_ok = within_abs(height, EXPECTED_THICKNESS, DIM_TOL)
    if plan_ok and thickness_ok:
        metrics["right_dimensions"] = True

    # right_location: center at (-30, 0) with tolerance, bottom ~ z=0 (loose)
    center_x_ok = within_abs(bbox["x_c"], CENTER_X, LOC_TOL)
    center_y_ok = within_abs(bbox["y_c"], CENTER_Y, LOC_TOL)
    bottom_ok = within_abs(bbox["z_c"], 0.0, Z_CENTER_TOL)

    if center_x_ok and center_y_ok and bottom_ok:
        metrics["right_location"] = True

    # integrity: average of sub-checks
    sub_checks = [
        check_is_correct_type(slab, "IfcSlab"),
        check_spatial_containment(ifc_edited, slab),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
