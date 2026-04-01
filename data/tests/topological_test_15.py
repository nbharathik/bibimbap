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


TARGET_GUID = "0CJwXarnHAeA7eFXxxI_is"
TARGET_DELTA_Z_MM = -50.0
POSITION_TOLERANCE = 0.1
UNIT_SCALE = 1.0
DIMENSION_TOLERANCE = 0.02


def _safe_by_guid(ifc_model, guid):
    try:
        return ifc_model.by_guid(guid)
    except Exception:
        return None


def _placement_xyz_mm(product):
    matrix = ifcopenshell.util.placement.get_local_placement(product.ObjectPlacement)
    return tuple(float(matrix[index][3]) for index in range(3))


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
        "x_len": x_max - x_min,
        "y_len": y_max - y_min,
        "z_len": z_max - z_min,
    }


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Change the position of the slab with id 0CJwXarnHAeA7eFXxxI_is
    so that it lays on the slab with id 0CJwXarnHAeA7eFXxxI_hO.

    Expected behavior:
    - The target slab keeps its X and Y placement.
    - The target slab moves down by 50 mm in Z.
    - No other rooted elements change.

    Metrics:
    - right_location: The target slab global placement is (same X, same Y, delta Z = -50.0).
    - right_dimensions: True because this task only changes position, not slab geometry.
    - integrity_constraint: Only the target slab changes and the model stays clash-free.
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

    original_slab = _safe_by_guid(ifc_original, TARGET_GUID)
    edited_slab = _safe_by_guid(ifc_edited, TARGET_GUID)
    if original_slab is None or edited_slab is None:
        return metrics

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[TARGET_GUID],
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        original_x, original_y, original_z = _placement_xyz_mm(original_slab)
        edited_x, edited_y, edited_z = _placement_xyz_mm(edited_slab)
    except Exception:
        return metrics

    # This benchmark variant accepts the task as a pure Z move of -50 mm while
    # preserving the X/Y placement of the target slab.
    metrics["right_location"] = (
        abs((edited_z - original_z) - TARGET_DELTA_Z_MM) <= POSITION_TOLERANCE
        and abs(edited_x - original_x) <= POSITION_TOLERANCE
        and abs(edited_y - original_y) <= POSITION_TOLERANCE
    )

    # Moving the slab should preserve its geometry; only the placement may change.
    try:
        original_bbox = _bbox_in_meters(original_slab, UNIT_SCALE)
        edited_bbox = _bbox_in_meters(edited_slab, UNIT_SCALE)
        metrics["right_dimensions"] = (
            abs(edited_bbox["x_len"] - original_bbox["x_len"]) <= DIMENSION_TOLERANCE
            and abs(edited_bbox["y_len"] - original_bbox["y_len"]) <= DIMENSION_TOLERANCE
            and abs(edited_bbox["z_len"] - original_bbox["z_len"]) <= DIMENSION_TOLERANCE
        )
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "02" / "01_02_015.ifc"
    edited_ifc_file = data_dir / "solutions" / "topological_15.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
