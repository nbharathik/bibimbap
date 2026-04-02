"""
Test 01 - Basic CREATE: Door in Wall
=====================================

Prompt:
    "Create a door with the size of 2 by 1 meters in the wall with id 2UsXAbj6n0fwEWqdkVuHvf."

IFC file: basic_tasks.ifc
Category: Basic / Create

What this test evaluates:
    The LLM must create exactly one new IfcDoor element and place it inside
    a specific wall. The door must have the correct dimensions and be
    topologically linked via the standard IFC relationship chain:
    IfcDoor → IfcRelFillsElement → IfcOpeningElement → IfcRelVoidsElement → IfcWall.

Metrics:
    object_exists (bool):
        True if exactly one new IfcDoor was created. If zero or more than one
        new door is found, the test returns early with only this metric set.

    right_dimensions (bool):
        True if the door dimensions are 2m × 1m (height × width). Since the
        prompt "2 by 1" is ambiguous, both orientations are accepted:
        (height=2, width=1) or (height=1, width=2). Tolerance: ±0.05m.

    right_location (bool):
        True if the door's bounding box fits entirely within the target wall's
        bounding box. Tolerance: ±0.1m.

    integrity_constraint (float, 0.0–1.0):
        Average of the following sub-checks (each 0.0 or 1.0):
          1. Correct IFC type - element is IfcDoor
          2. Fills/Voids chain - door fills an opening that voids the target wall
          3. Spatial containment - door is assigned to a storey via
              IfcRelContainedInSpatialStructure
          4. Elements preserved - all original GUIDs still exist in the edited model
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, get_shape_dims, within_abs, dims_match,
    bbox_contains_bbox, compute_integrity,    check_spatial_containment,
    check_elements_preserved, check_fills_voids_chain,
)
from .utils.clash_utils import check_clash_integrity


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a door with the size of 2 by 1 meters in the wall with id 2UsXAbj6n0fwEWqdkVuHvf."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    WALL_GUID = "2UsXAbj6n0fwEWqdkVuHvf"
    EXPECTED_DIMS = (2.0, 1.0)  # height x width - accept both orientations
    DIM_TOL = 0.05

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # get wall bounding box
    wall = ifc_edited.by_guid(WALL_GUID)
    try:
        wall_bbox = get_bbox(wall)
    except RuntimeError:
        return metrics

    # find new doors - must be exactly one
    new_doors = find_new_elements(ifc_original, ifc_edited, "IfcDoor")
    if not new_doors:
        return metrics

    metrics["object_exists"] = True

    if len(new_doors) != 1:
        return metrics

    door = new_doors[0]

    try:
        door_bbox = get_bbox(door)
    except RuntimeError:
        return metrics

    shape_dims = get_shape_dims(door)
    if shape_dims is None:
        return metrics
    width, depth, height = shape_dims

    # right_dimensions: accept both (2x1) and (1x2) orientations
    if dims_match((height, width), EXPECTED_DIMS, DIM_TOL) or \
       dims_match((height, depth), EXPECTED_DIMS, DIM_TOL):
        metrics["right_dimensions"] = True

    # right_location: door bounding box is inside wall bounding box
    if bbox_contains_bbox(wall_bbox, door_bbox, tol=0.1):
        metrics["right_location"] = True

    # integrity: average of sub-checks
    sub_checks = [
        check_fills_voids_chain(ifc_edited, door, wall),
        check_spatial_containment(ifc_edited, door),
        check_clash_integrity(ifc_original, ifc_edited, list_of_targets=[door.GlobalId], clash_mode="collision"),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
