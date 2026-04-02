"""
Test 03 - Basic CREATE: Opening in Slab
=========================================

Prompt:
    "Add an opening of size 5 by 5 meters to the center of the slab
    with id 11kJIqz$n2Jf_DfJV1SCVP."

IFC file: basic_tasks.ifc
Category: Basic / Create

What this test evaluates:
    The LLM must create exactly one new IfcOpeningElement, size it to 5m × 5m,
    center it on the target slab, and link it via IfcRelVoidsElement so that the
    opening correctly voids the slab.

Metrics:
    object_exists (bool):
        True if exactly one new IfcOpeningElement was created. If zero or more
        than one is found, the test returns early with only this metric set.

    right_dimensions (bool):
        True if the opening plan dimensions are 5m × 5m (either orientation
        accepted). Tolerance: ±0.05m.

    right_location (bool):
        True if the opening is centered on the slab. Centering is checked by
        verifying that the gap between the slab edge and opening edge is equal
        on both sides in X and Y (within ±0.5m). Additionally, the opening
        must intersect the slab in the Z-axis (go through it).

    integrity_constraint (float, 0.0–1.0):
        Average of the following sub-checks (each 0.0 or 1.0):
        1. Correct IFC type - element is IfcOpeningElement
        2. Voids relationship - IfcRelVoidsElement links the opening to the slab
        3. Elements preserved - all original GUIDs still exist
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, get_shape_dims, within_abs, dims_match,
    compute_integrity,    check_elements_preserved, check_voids_relationship,
)
from .utils.clash_utils import check_clash_integrity


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add an opening of size 5 by 5 meters to the center of the slab with id 11kJIqz$n2Jf_DfJV1SCVP."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    SLAB_GUID = "11kJIqz$n2Jf_DfJV1SCVP"
    EXPECTED_DIMS = (5.0, 5.0)
    DIM_TOL = 0.05
    CENTER_TOL = 0.5

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # get slab bounding box
    slab = ifc_edited.by_guid(SLAB_GUID)
    try:
        slab_bbox = get_bbox(slab)
    except RuntimeError:
        return metrics

    # find new openings - must be exactly one
    new_openings = find_new_elements(ifc_original, ifc_edited, "IfcOpeningElement")
    if not new_openings:
        return metrics

    metrics["object_exists"] = True

    if len(new_openings) != 1:
        return metrics

    opening = new_openings[0]

    try:
        opening_bbox = get_bbox(opening)
    except RuntimeError:
        return metrics

    shape_dims = get_shape_dims(opening)
    if shape_dims is None:
        return metrics
    width, depth, height = shape_dims

    # right_dimensions: 5x5 in plan (accept both orientations)
    if dims_match((width, depth), EXPECTED_DIMS, DIM_TOL):
        metrics["right_dimensions"] = True

    # right_location: opening centered on slab (equal distance from each edge)
    dx_min = abs(slab_bbox["x_min"] - opening_bbox["x_min"])
    dx_max = abs(slab_bbox["x_max"] - opening_bbox["x_max"])
    dy_min = abs(slab_bbox["y_min"] - opening_bbox["y_min"])
    dy_max = abs(slab_bbox["y_max"] - opening_bbox["y_max"])

    centered_x = within_abs(dx_min, dx_max, CENTER_TOL)
    centered_y = within_abs(dy_min, dy_max, CENTER_TOL)

    # opening should go through the slab in z
    through_z = (opening_bbox["z_min"] <= slab_bbox["z_max"] and
                 opening_bbox["z_max"] >= slab_bbox["z_min"])

    if centered_x and centered_y and through_z:
        metrics["right_location"] = True

    # integrity: voids relationship + valid representation + elements preserved
    sub_checks = [
        check_voids_relationship(ifc_edited, opening, slab),
        check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[opening.GlobalId], clash_mode="collision"),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
