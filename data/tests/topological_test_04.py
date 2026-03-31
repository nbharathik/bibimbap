"""
Topological Test 04 - CREATE: Slab Closing Walls
==================================================

Prompt:
    "Create a slab that closes the elements with the ids
    3_DHXxtdb3wRKlXgyMiHR$, 3_DHXxtdb3wRKlXgyMiHOP,
    3_DHXxtdb3wRKlXgyMiH5o, 1IMYx2Ej12vu3iYKHoTn08."

IFC file: 01/02/01_02_004.ifc
Category: Topological / Create

What this test evaluates:
    The LLM must create exactly one new IfcSlab that covers the area enclosed
    by the 4 referenced walls, positioned at the top or bottom of the walls.

Metrics:
    object_exists (bool):
        True if exactly one new IfcSlab was created.

    right_dimensions (bool):
        True if the slab dimensions match the enclosed area (±1m per dimension
        or within 20% of the area).

    right_location (bool):
        True if the slab is at floor or ceiling level of the walls AND
        overlaps with the enclosed area in the XY plane.

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
    """Prompt: Create a slab that closes the elements with the ids [3_DHXxtdb3wRKlXgyMiHR$, 3_DHXxtdb3wRKlXgyMiHOP, 3_DHXxtdb3wRKlXgyMiH5o, 1IMYx2Ej12vu3iYKHoTn08]."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    WALL_IDS = ["3_DHXxtdb3wRKlXgyMiHR$", "3_DHXxtdb3wRKlXgyMiHOP",
                "3_DHXxtdb3wRKlXgyMiH5o", "1IMYx2Ej12vu3iYKHoTn08"]
    TOL = 1.0

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

    slab_dims = get_shape_dims(slab)
    if slab_dims is None:
        return metrics
    slab_width, slab_depth, slab_thickness = slab_dims

    # get wall bounding boxes
    wall_bboxes = []
    for wall_id in WALL_IDS:
        try:
            wall = ifc_edited.by_guid(wall_id)
            wall_bboxes.append(get_bbox(wall))
        except RuntimeError:
            continue

    if len(wall_bboxes) >= 4:
        x_min_space = min(wb["x_min"] for wb in wall_bboxes)
        x_max_space = max(wb["x_max"] for wb in wall_bboxes)
        y_min_space = min(wb["y_min"] for wb in wall_bboxes)
        y_max_space = max(wb["y_max"] for wb in wall_bboxes)
        z_max_walls = max(wb["z_max"] for wb in wall_bboxes)
        z_min_walls = min(wb["z_min"] for wb in wall_bboxes)

        space_width = x_max_space - x_min_space
        space_depth = y_max_space - y_min_space

        # right_dimensions
        slab_area = slab_width * slab_depth
        space_area = space_width * space_depth

        if (within_abs(slab_width, space_width, TOL) and within_abs(slab_depth, space_depth, TOL)):
            metrics["right_dimensions"] = True
        elif space_area > 0 and abs(slab_area - space_area) < (space_area * 0.2):
            metrics["right_dimensions"] = True

        # right_location: at floor or ceiling + overlaps in XY
        slab_z_center = slab_bbox["z_c"]
        at_floor = within_abs(slab_z_center, z_min_walls, TOL)
        at_ceiling = within_abs(slab_z_center, z_max_walls, TOL)

        x_overlap = not (slab_bbox["x_max"] < x_min_space - TOL or slab_bbox["x_min"] > x_max_space + TOL)
        y_overlap = not (slab_bbox["y_max"] < y_min_space - TOL or slab_bbox["y_min"] > y_max_space + TOL)

        if (at_floor or at_ceiling) and x_overlap and y_overlap:
            metrics["right_location"] = True

    # integrity
    sub_checks = [
        check_is_correct_type(slab, "IfcSlab"),
        check_spatial_containment(ifc_edited, slab),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
