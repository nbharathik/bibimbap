"""
Geometry Test 03 - CREATE: Door on North Wall
===============================================

Prompt:
    "Add a door to the wall that is north (+Y direction) of the wall
    with GlobalId = '3YQ$1CPXD2Mh2vQ18vV$hw'."

IFC file: 01/01/01_01_003.ifc
Category: Geometry / Create

What this test evaluates:
    The LLM must create exactly one new IfcDoor, place it on the wall that
    is directly north (+Y) of the referenced wall, with its base at ground
    level. The door must have a proper opening relationship (IfcRelFillsElement).

Metrics:
    object_exists (bool):
        True if exactly one new IfcDoor was created.

    right_dimensions (bool):
        True if the door has reasonable dimensions (width 0.6-1.5m, height 1.5-3.0m).
        No specific dimensions are given in the prompt.

    right_location (bool):
        True if the door is placed on the north wall (closest wall in +Y from
        the referenced wall) AND its base is at ground level (z_min ~0).

    integrity_constraint (float, 0.0-1.0):
        Average of: correct IFC type + fills/voids chain (door fills an opening
        that voids the north wall) + elements preserved.
"""

import ifcopenshell
from .utils.create_utils import (
    find_new_elements, get_bbox, within_abs, bbox_contains_bbox,
    compute_integrity, check_is_correct_type,
    check_fills_voids_chain, check_elements_preserved,
)


def _find_north_wall(walls, target_guid):
    """Find the wall directly north (+Y) of the target wall."""
    target = next((w for w in walls if w.GlobalId == target_guid), None)
    if target is None:
        return None, None, None

    try:
        target_bbox = get_bbox(target)
    except RuntimeError:
        return None, None, None

    target_y_c = target_bbox["y_c"]

    north_candidates = []
    for wall in walls:
        if wall.GlobalId == target_guid:
            continue
        try:
            bbox = get_bbox(wall)
        except RuntimeError:
            continue
        delta_y = bbox["y_c"] - target_y_c
        if delta_y > 0:
            north_candidates.append((delta_y, wall, bbox))

    if not north_candidates:
        return None, target_bbox, None

    north_candidates.sort(key=lambda item: item[0])
    _, north_wall, north_bbox = north_candidates[0]
    return north_wall, north_bbox, target_bbox


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add a door to the wall that is north (+Y direction) of the wall with GlobalId = '3YQ$1CPXD2Mh2vQ18vV$hw'."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": 0.0,
    }

    TARGET_GUID = "3YQ$1CPXD2Mh2vQ18vV$hw"
    EXISTING_DOOR_GUIDS = {"3YQ$1CPXD2Mh2vQ18vV$hw", "3YQ$1CPXD2Mh2vQ18vV$ig", "3YQ$1CPXD2Mh2vQ18vV$iC"}

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # find new doors (exclude existing ones)
    all_doors = ifc_edited.by_type("IfcDoor")
    new_doors = [d for d in all_doors if d.GlobalId not in EXISTING_DOOR_GUIDS
                 and d.GlobalId not in {dd.GlobalId for dd in ifc_original.by_type("IfcDoor")}]

    if not new_doors:
        # fallback: use find_new_elements
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
    door_width = door_bbox["x_len"]
    door_depth = door_bbox["y_len"]
    door_height = door_bbox["z_len"]
    if (0.6 <= door_width <= 1.5 and 1.5 <= door_height <= 3.0) or \
       (0.6 <= door_depth <= 1.5 and 1.5 <= door_height <= 3.0):
        metrics["right_dimensions"] = True

    # find the north wall
    walls = ifc_edited.by_type("IfcWallStandardCase") or ifc_edited.by_type("IfcWall")
    if not walls:
        walls = ifc_edited.by_type("IfcWall")

    north_wall, north_bbox, target_bbox = _find_north_wall(walls, TARGET_GUID)
    if north_wall is None or north_bbox is None or target_bbox is None:
        sub_checks = [
            check_is_correct_type(door, "IfcDoor"),
            check_elements_preserved(ifc_original, ifc_edited),
        ]
        metrics["integrity_constraint"] = compute_integrity(sub_checks)
        return metrics

    # right_location: door in north wall plane + base at ground
    tol_y = 0.1
    tol_x = 0.25

    in_wall_plane = (
        north_bbox["y_min"] - tol_y <= door_bbox["y_min"] <= north_bbox["y_max"] + tol_y
        and north_bbox["y_min"] - tol_y <= door_bbox["y_max"] <= north_bbox["y_max"] + tol_y
    )
    within_span_x = (
        door_bbox["x_min"] <= north_bbox["x_max"] + tol_x
        and door_bbox["x_max"] >= north_bbox["x_min"] - tol_x
    )

    dist_to_north = abs(door_bbox["y_c"] - north_bbox["y_c"])
    dist_to_target = abs(door_bbox["y_c"] - target_bbox["y_c"])

    on_north_wall = in_wall_plane and within_span_x and dist_to_north < dist_to_target
    base_at_ground = within_abs(door_bbox["z_min"], 0.0, tol=0.1)

    if on_north_wall and base_at_ground:
        metrics["right_location"] = True

    # integrity: fills/voids chain to north wall
    sub_checks = [
        check_is_correct_type(door, "IfcDoor"),
        check_fills_voids_chain(ifc_edited, door, north_wall),
        check_elements_preserved(ifc_original, ifc_edited),
    ]
    metrics["integrity_constraint"] = compute_integrity(sub_checks)

    return metrics
