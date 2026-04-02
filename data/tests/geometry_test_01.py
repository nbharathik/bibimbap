"""
Geometry Test 01 - CREATE: Slab on Columns
============================================

Prompt:
    "Create a slab that has a width of 0.2m and is placed on the upper
    outer edges of the four columns in the IFC file."

IFC file: 01/01/01_01_001.ifc
Category: Geometry / Create

What this test evaluates:
    The LLM must create exactly one new IfcSlab with thickness 0.2m, placed
    on top of the 4 existing columns. The slab footprint must span the outer
    faces of the columns (not just be centered somewhere).

Metrics:
    object_exists (bool):
        True if exactly one new IfcSlab was created.

    right_dimensions (bool):
        True if the slab's thinnest extent is ~0.2m. Tolerance: ±0.02m.

    right_location (bool):
        True if the slab bottom sits on the column tops AND the slab
        footprint spans the outer edges of all 4 columns (±0.5m overhang max).

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
    """Prompt: Create a slab that has a width of 0.2m and is placed on the upper outer edges of the 4 columns in the IFC file."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

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
        slab_bbox = get_bbox(slab)
    except RuntimeError:
        return metrics

    # right_dimensions: thickness (thinnest extent) ~0.2m
    extents = [slab_bbox["x_len"], slab_bbox["y_len"], slab_bbox["z_len"]]
    thickness_est = min(extents)
    if within_abs(thickness_est, 0.2, tol=0.02):
        metrics["right_dimensions"] = True

    # get column bounding boxes
    columns = ifc_edited.by_type("IfcColumn")
    if len(columns) < 4:
        # integrity still computed below
        sub_checks = [
            check_spatial_containment(ifc_edited, slab),
            check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[slab.GlobalId], clash_mode="collision"),
            check_elements_preserved(ifc_original, ifc_edited),
        ]
        metrics["integrity_constraint"] = compute_integrity(sub_checks)
        return metrics

    col_bboxes = []
    for col in columns:
        try:
            col_bboxes.append(get_bbox(col))
        except RuntimeError:
            continue

    if len(col_bboxes) < 4:
        sub_checks = [
            check_spatial_containment(ifc_edited, slab),
            check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[slab.GlobalId], clash_mode="collision"),
            check_elements_preserved(ifc_original, ifc_edited),
        ]
        metrics["integrity_constraint"] = compute_integrity(sub_checks)
        return metrics

    # right_location: slab bottom on column tops + spans outer edges
    top_z = max(b["z_max"] for b in col_bboxes)
    min_x_edge = min(b["x_min"] for b in col_bboxes)
    max_x_edge = max(b["x_max"] for b in col_bboxes)
    min_y_edge = min(b["y_min"] for b in col_bboxes)
    max_y_edge = max(b["y_max"] for b in col_bboxes)

    tol_z = 0.05
    tol_edge = 0.05
    max_overhang = 0.50

    on_top = within_abs(slab_bbox["z_min"], top_z, tol_z)

    spans_outer = (
        slab_bbox["x_min"] <= min_x_edge + tol_edge
        and slab_bbox["x_max"] >= max_x_edge - tol_edge
        and slab_bbox["y_min"] <= min_y_edge + tol_edge
        and slab_bbox["y_max"] >= max_y_edge - tol_edge
    )

    not_too_large = (
        slab_bbox["x_min"] >= min_x_edge - max_overhang
        and slab_bbox["x_max"] <= max_x_edge + max_overhang
        and slab_bbox["y_min"] >= min_y_edge - max_overhang
        and slab_bbox["y_max"] <= max_y_edge + max_overhang
    )

    if on_top and spans_outer and not_too_large:
        metrics["right_location"] = True

    # integrity
    sub_checks = [
        check_spatial_containment(ifc_edited, slab),
        check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[slab.GlobalId], clash_mode="collision"),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
