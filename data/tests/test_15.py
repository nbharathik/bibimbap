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


COLUMN_GUID = "22hyxvAPr65PFt9WZfHSMu"
EXPECTED_DELTA_Y_M = -3.0
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


def _moved_in_y_by_expected_delta(original_product, edited_product):
    original_x, original_y, original_z = _placement_xyz_m(original_product)
    edited_x, edited_y, edited_z = _placement_xyz_m(edited_product)
    return (
        _within_abs(edited_x - original_x, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_y - original_y, EXPECTED_DELTA_Y_M, POSITION_TOLERANCE_M)
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
    """Prompt: Move the column with id 22hyxvAPr65PFt9WZfHSMu by -3 meters in direction of y.

    Expected behavior:
    - The target column is translated by -3.0 m along the global Y axis.
    - The column keeps the same geometry while its placement changes only along Y.

    Metrics:
    - right_location: The column moves by -3.0 m in Y without X/Z drift.
    - right_dimensions: The moved column keeps the same dimensions.
    - integrity_constraint: Only the target column changes and the edited model remains valid.
    """
    del model_output

    base_metrics = {
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return base_metrics

    original_column = _safe_by_guid(ifc_original, COLUMN_GUID)
    edited_column = _safe_by_guid(ifc_edited, COLUMN_GUID)
    if original_column is None or edited_column is None:
        return base_metrics

    # Evaluate integrity independently of task scoring once the files and target are valid.
    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[COLUMN_GUID],
    )
    base_metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        # The task is a pure translation, so placement and geometry are validated separately.
        base_metrics["right_location"] = _moved_in_y_by_expected_delta(original_column, edited_column)
        base_metrics["right_dimensions"] = _dimensions_unchanged(original_column, edited_column)
    except Exception:
        return base_metrics

    return base_metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "basic_tasks.ifc"
    edited_ifc_file = data_dir / "solutions" / "test_15.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
