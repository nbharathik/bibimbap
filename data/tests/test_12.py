from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity
from data.updated_tests._integrity_utils import filled_opening_guid


DOOR_GUID = "11kJIqz$n2Jf_DfJV1SDY7"
OPENING_GUID_FALLBACK = "1U$$kq6emLyOkmIlVkRzzn"
EXPECTED_DELTA_X_M = -1.0
POSITION_TOLERANCE_M = 0.1
DIMENSION_TOLERANCE_M = 0.1


def _safe_by_guid(ifc_model, guid):
    try:
        return ifc_model.by_guid(guid)
    except Exception:
        return None


def _placement_xyz_m(product):
    matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
    return tuple(float(matrix[index][3]) / 1000.0 for index in range(3))


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
    }


def _within_abs(value, expected, tolerance):
    return abs(value - expected) <= tolerance


def _moved_by_expected_delta(original_product, edited_product):
    original_x, original_y, original_z = _placement_xyz_m(original_product)
    edited_x, edited_y, edited_z = _placement_xyz_m(edited_product)
    return (
        _within_abs(edited_x - original_x, EXPECTED_DELTA_X_M, POSITION_TOLERANCE_M)
        and _within_abs(edited_y - original_y, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_z - original_z, 0.0, POSITION_TOLERANCE_M)
    )


def _dimensions_unchanged(original_product, edited_product):
    original_bbox = _bbox_in_meters(original_product)
    edited_bbox = _bbox_in_meters(edited_product)
    return (
        _within_abs(edited_bbox["x_len"], original_bbox["x_len"], DIMENSION_TOLERANCE_M)
        and _within_abs(edited_bbox["y_len"], original_bbox["y_len"], DIMENSION_TOLERANCE_M)
        and _within_abs(edited_bbox["z_len"], original_bbox["z_len"], DIMENSION_TOLERANCE_M)
    )


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Move the door by one meter in direction of x in the wall with id
    11kJIqz$n2Jf_DfJV1SDYu.

    Expected behavior:
    - The target door moves by exactly 1 meter along the negative X direction.
    - The door keeps its dimensions.
    - The filled opening moves with the door.

    Metrics:
    - right_location: The target door moved by -1.0 m in X and not in Y/Z.
    - right_dimensions: The door geometry remains unchanged.
    - integrity_constraint: Only the door and its opening change and the model stays
      clash-free.
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

    original_door = _safe_by_guid(ifc_original, DOOR_GUID)
    edited_door = _safe_by_guid(ifc_edited, DOOR_GUID)
    opening_guid = filled_opening_guid(ifc_original, DOOR_GUID) or OPENING_GUID_FALLBACK
    original_opening = _safe_by_guid(ifc_original, opening_guid)
    edited_opening = _safe_by_guid(ifc_edited, opening_guid)

    if original_door is None or edited_door is None or original_opening is None or edited_opening is None:
        return metrics

    # Evaluate integrity independently of task scoring once the files and targets are valid.
    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[DOOR_GUID, opening_guid],
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        metrics["right_location"] = _moved_by_expected_delta(original_door, edited_door)
        metrics["right_dimensions"] = _dimensions_unchanged(original_door, edited_door)
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "basic_tasks.ifc"
    edited_ifc_file = data_dir / "solutions" / "test_12.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
