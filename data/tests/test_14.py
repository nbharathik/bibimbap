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


SLAB_GUID = "11kJIqz$n2Jf_DfJV1SCVP"
EXPECTED_DELTA_Z_M = -0.5
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


def _moved_down_by_expected_delta(original_product, edited_product):
    original_x, original_y, original_z = _placement_xyz_m(original_product)
    edited_x, edited_y, edited_z = _placement_xyz_m(edited_product)
    return (
        _within_abs(edited_x - original_x, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_y - original_y, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_z - original_z, EXPECTED_DELTA_Z_M, POSITION_TOLERANCE_M)
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
    """Prompt: Decrease the height by 0.5 meters of the slab with the id
    11kJIqz$n2Jf_DfJV1SCVP.

    Expected behavior:
    - In this benchmark, the intended result is that the slab is moved down by 0.5 m.
    - The slab keeps the same geometry while its placement changes only along Z.

    Metrics:
    - right_location: The slab moves down by 0.5 m without X/Y drift.
    - right_dimensions: The slab keeps the same dimensions.
    - integrity_constraint: Only the target slab changes and the edited model remains valid.
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

    original_slab = _safe_by_guid(ifc_original, SLAB_GUID)
    edited_slab = _safe_by_guid(ifc_edited, SLAB_GUID)
    if original_slab is None or edited_slab is None:
        return base_metrics

    # Evaluate integrity independently of task scoring once the files and target are valid.
    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[SLAB_GUID],
    )

    ## in this case if implemented correctly, there is still a clash between the slab and a wall. Therefore, the integrity constraint is true, even if there is a clash.
    base_metrics["integrity_constraint"] = bool(result.get("non_target_elements_unchanged", False))

    


    try:
        # The task is a pure translation, so location and dimensions are checked separately.
        base_metrics["right_location"] = _moved_down_by_expected_delta(original_slab, edited_slab)
        base_metrics["right_dimensions"] = _dimensions_unchanged(original_slab, edited_slab)
    except Exception:
        return base_metrics

    return base_metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "basic_tasks.ifc"
    edited_ifc_file = data_dir / "solutions" / "test_14.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
