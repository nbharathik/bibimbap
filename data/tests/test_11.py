from pathlib import Path
import math
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


TARGET_GUID = "22hyxvAPr65PFt9WZfHSP3"
ROTATION_TOLERANCE_DEG = 1.0
CENTER_TOLERANCE_M = 0.05
DIMENSION_TOLERANCE_M = 0.05


def _bbox_in_meters(product):
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, product)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)

    x_min = float(vertices[:, 0].min())
    x_max = float(vertices[:, 0].max())
    y_min = float(vertices[:, 1].min())
    y_max = float(vertices[:, 1].max())
    z_min = float(vertices[:, 2].min())
    z_max = float(vertices[:, 2].max())

    return {
        "x_len": x_max - x_min,
        "y_len": y_max - y_min,
        "z_len": z_max - z_min,
        "x_center": (x_min + x_max) / 2.0,
        "y_center": (y_min + y_max) / 2.0,
        "z_center": (z_min + z_max) / 2.0,
    }


def _within_abs(value, expected, tolerance):
    return abs(value - expected) <= tolerance


def _safe_by_guid(ifc_model, guid):
    try:
        return ifc_model.by_guid(guid)
    except Exception:
        return None


def _plan_angle_deg(product):
    # Use the local X axis of the placement as the wall direction proxy in plan.
    matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
    x_axis = np.array(matrix[:2, 0], dtype=float)
    return math.degrees(math.atan2(x_axis[1], x_axis[0])) % 180.0


def _angle_difference_deg(angle_1, angle_2):
    difference = abs(angle_1 - angle_2) % 180.0
    if difference > 90.0:
        difference = 180.0 - difference
    return difference


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Rotate the wall with id 22hyxvAPr65PFt9WZfHSP3 by +90° around the z axis.

    Expected behavior:
    - The target wall still exists after the edit.
    - The wall rotates by 90 degrees in plan.
    - The wall rotates about its center, so the bbox center stays unchanged.
    - The wall keeps its original dimensions.

    Metrics:
    - right_location: The wall center stays fixed and the wall rotates by 90°.
    - right_dimensions: The wall height is unchanged and the footprint extents swap.
    - integrity_constraint: Only the target wall changes and the model stays clash-free.
    """
    del model_output

    metrics = {
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    original_wall = _safe_by_guid(ifc_original, TARGET_GUID)
    edited_wall = _safe_by_guid(ifc_edited, TARGET_GUID)
    if original_wall is None or edited_wall is None:
        return metrics

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[TARGET_GUID],
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        original_bbox = _bbox_in_meters(original_wall)
        edited_bbox = _bbox_in_meters(edited_wall)
        original_angle = _plan_angle_deg(original_wall)
        edited_angle = _plan_angle_deg(edited_wall)
    except Exception:
        return metrics

    # A correct in-place rotation keeps the center fixed while changing the plan
    # orientation by 90 degrees.
    metrics["right_location"] = (
        _within_abs(edited_bbox["x_center"], original_bbox["x_center"], CENTER_TOLERANCE_M)
        and _within_abs(edited_bbox["y_center"], original_bbox["y_center"], CENTER_TOLERANCE_M)
        and _within_abs(edited_bbox["z_center"], original_bbox["z_center"], CENTER_TOLERANCE_M)
        and _within_abs(
            _angle_difference_deg(edited_angle, original_angle),
            90.0,
            ROTATION_TOLERANCE_DEG,
        )
    )

    # Rotating a rectangular wall by 90 degrees swaps its plan extents while
    # preserving the height.
    metrics["right_dimensions"] = (
        _within_abs(edited_bbox["z_len"], original_bbox["z_len"], DIMENSION_TOLERANCE_M)
        and _within_abs(edited_bbox["x_len"], original_bbox["y_len"], DIMENSION_TOLERANCE_M)
        and _within_abs(edited_bbox["y_len"], original_bbox["x_len"], DIMENSION_TOLERANCE_M)
    )

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "basic_tasks.ifc"
    edited_ifc_file = data_dir / "solutions" / "test_11.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
