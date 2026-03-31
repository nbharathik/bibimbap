"""
Topological Test 05 - CREATE: Door Connecting Inner/Outer Space
================================================================

Prompt:
    "Create a door in one of the existing walls so that it connects
    the inner space with the outdoor space."

IFC file: 01/02/01_02_005.ifc
Category: Topological / Create

What this test evaluates:
    The LLM must create exactly one new IfcDoor in an existing wall,
    with a proper opening relationship (IfcRelFillsElement → IfcOpeningElement
    → IfcRelVoidsElement → IfcWall). The door should have reasonable
    dimensions for an exterior door.

Metrics:
    object_exists (bool):
        True if exactly one new IfcDoor was created.

    right_dimensions (bool):
        True if the door has reasonable dimensions (width 0.6-1.5m,
        height 1.5-3.0m). No specific dimensions are given.

    right_location (bool):
        True if the door is geometrically located inside one of the
        existing walls (bounding box containment or fills/voids chain).

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + fills/voids chain (door fills an
        opening that voids a wall) + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, bbox_contains_bbox,
    compute_integrity, check_is_correct_type,
    check_elements_preserved,
)


def _find_door_wall_via_chain(model, door):
    """Find the wall that the door is in via IfcRelFillsElement → IfcRelVoidsElement chain."""
    try:
        for rel_fills in model.by_type("IfcRelFillsElement"):
            if rel_fills.RelatedBuildingElement != door:
                continue
            opening = rel_fills.RelatingOpeningElement
            if not opening or not opening.is_a("IfcOpeningElement"):
                continue
            for rel_voids in model.by_type("IfcRelVoidsElement"):
                if rel_voids.RelatedOpeningElement == opening and rel_voids.RelatingBuildingElement:
                    if rel_voids.RelatingBuildingElement.is_a("IfcWall"):
                        return rel_voids.RelatingBuildingElement
    except RuntimeError:
        pass
    return None


def _check_fills_voids_any_wall(model, door):
    """Check if door fills an opening that voids ANY wall. Returns 1.0 or 0.0."""
    return 1.0 if _find_door_wall_via_chain(model, door) is not None else 0.0


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a door in one of the existing walls so that it connects the inner space with the outdoor space."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

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

    # right_dimensions: reasonable door size
    door_w = door_bbox["x_len"]
    door_d = door_bbox["y_len"]
    door_h = door_bbox["z_len"]
    if (0.6 <= door_w <= 1.5 and 1.5 <= door_h <= 3.0) or \
       (0.6 <= door_d <= 1.5 and 1.5 <= door_h <= 3.0):
        metrics["right_dimensions"] = True

    # right_location: door is in a wall (via chain or geometric fallback)
    door_in_wall = False

    # method 1: relationship chain
    host_wall = _find_door_wall_via_chain(ifc_edited, door)
    if host_wall is not None:
        door_in_wall = True

    # method 2: geometric fallback
    if not door_in_wall:
        for wall in ifc_edited.by_type("IfcWall"):
            try:
                wall_bbox = get_bbox(wall)
                if bbox_contains_bbox(wall_bbox, door_bbox, tol=0.1):
                    door_in_wall = True
                    break
            except RuntimeError:
                continue

    if door_in_wall:
        metrics["right_location"] = True

    # integrity
    sub_checks = [
        check_is_correct_type(door, "IfcDoor"),
        _check_fills_voids_any_wall(ifc_edited, door),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
