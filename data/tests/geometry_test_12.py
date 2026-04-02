from pathlib import Path
import math
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


TARGET_WALL_GUID = "1$zxNs50z3OeFBpABtoN6K"
REFERENCE_WALL_GUID = "1$zxNs50z3OeFBpABtoN40"

UNIT_SCALE = 1.0
ROTATION_ANGLE = 45.0
ANGLE_TOLERANCE = 1.0
CENTER_TOLERANCE = 0.05
HEIGHT_TOLERANCE = 0.05


def _bbox_in_meters(product, unit_scale):
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, product)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    vertices = vertices * unit_scale

    x_min = float(vertices[:, 0].min())
    x_max = float(vertices[:, 0].max())
    y_min = float(vertices[:, 1].min())
    y_max = float(vertices[:, 1].max())
    z_min = float(vertices[:, 2].min())
    z_max = float(vertices[:, 2].max())

    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "z_min": z_min,
        "z_max": z_max,
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


def _load_models(ifc_file, edited_ifc_file):
    try:
        return ifcopenshell.open(ifc_file), ifcopenshell.open(edited_ifc_file)
    except Exception:
        return None, None


def _get_wall_direction_angle(wall, unit_scale):
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, wall)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    vertices = vertices * unit_scale
    xy_vertices = vertices[:, :2]

    max_distance = 0.0
    point_1 = None
    point_2 = None
    for index_1 in range(len(xy_vertices)):
        for index_2 in range(index_1 + 1, len(xy_vertices)):
            distance = np.linalg.norm(xy_vertices[index_1] - xy_vertices[index_2])
            if distance > max_distance:
                max_distance = distance
                point_1 = xy_vertices[index_1]
                point_2 = xy_vertices[index_2]

    direction = point_2 - point_1
    return math.degrees(math.atan2(direction[1], direction[0])) % 180


def _angle_difference(angle_1, angle_2):
    difference = abs(angle_1 - angle_2) % 180
    if difference > 90:
        difference = 180 - difference
    return difference


def _rotation_and_reference_ok(
    target_original,
    target_edited,
    reference_original,
    reference_edited,
):
    angle_original = _get_wall_direction_angle(target_original, UNIT_SCALE)
    angle_edited = _get_wall_direction_angle(target_edited, UNIT_SCALE)
    reference_angle_original = _get_wall_direction_angle(reference_original, UNIT_SCALE)
    reference_angle_edited = _get_wall_direction_angle(reference_edited, UNIT_SCALE)

    rotation_diff = _angle_difference(angle_edited, angle_original)
    reference_unchanged = _within_abs(
        reference_angle_edited,
        reference_angle_original,
        ANGLE_TOLERANCE,
    )
    return (
        _within_abs(rotation_diff, ROTATION_ANGLE, ANGLE_TOLERANCE)
        and reference_unchanged
    )


def _dimensions_and_center_ok(target_original, target_edited):
    bbox_original = _bbox_in_meters(target_original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(target_edited, UNIT_SCALE)

    dimensions_ok = _within_abs(
        bbox_original["z_len"],
        bbox_edited["z_len"],
        HEIGHT_TOLERANCE,
    )
    center_ok = (
        _within_abs(
            bbox_original["x_center"],
            bbox_edited["x_center"],
            CENTER_TOLERANCE,
        )
        and _within_abs(
            bbox_original["y_center"],
            bbox_edited["y_center"],
            CENTER_TOLERANCE,
        )
        and _within_abs(
            bbox_original["z_center"],
            bbox_edited["z_center"],
            CENTER_TOLERANCE,
        )
    )
    return dimensions_ok, center_ok


def execute_test(ifc_file, edited_ifc_file, model_output):
    del model_output

    metrics = {
        "integrity_constraint": False,
        "right_dimensions": False,
        "right_location": False,
    }

    ifc_original, ifc_edited = _load_models(ifc_file, edited_ifc_file)
    if ifc_original is None or ifc_edited is None:
        return metrics

    target_original = _safe_by_guid(ifc_original, TARGET_WALL_GUID)
    target_edited = _safe_by_guid(ifc_edited, TARGET_WALL_GUID)
    reference_original = _safe_by_guid(ifc_original, REFERENCE_WALL_GUID)
    reference_edited = _safe_by_guid(ifc_edited, REFERENCE_WALL_GUID)

    if None in (
        target_original,
        target_edited,
        reference_original,
        reference_edited,
    ):
        return metrics

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[TARGET_WALL_GUID],
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        metrics["right_dimensions"], metrics["right_location"] = _dimensions_and_center_ok(
            target_original,
            target_edited,
        )
        metrics["right_location"] = metrics["right_location"] and _rotation_and_reference_ok(
            target_original,
            target_edited,
            reference_original,
            reference_edited,
        )
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "01" / "01_01_012.ifc"
    edited_ifc_file = data_dir / "solutions" / "geometry_12.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
