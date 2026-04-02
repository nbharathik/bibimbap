from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


SLAB_GUID = "11kJIqz$n2Jf_DfJV1SCVP"

UNIT_SCALE = 1.0
SQUARE_TOLERANCE = 0.2
Y_INCREASE_EXPECTED = 1.5
Y_INCREASE_TOLERANCE = 0.2
THICKNESS_TOLERANCE = 0.05
CENTER_TOLERANCE = 0.05


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


def _dimensions_ok(slab_original, slab_edited):
    bbox_original = _bbox_in_meters(slab_original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(slab_edited, UNIT_SCALE)

    y_increase = bbox_edited["y_len"] - bbox_original["y_len"]
    y_increased_correctly = _within_abs(
        y_increase,
        Y_INCREASE_EXPECTED,
        Y_INCREASE_TOLERANCE,
    )
    is_square = _within_abs(
        bbox_edited["x_len"],
        bbox_edited["y_len"],
        SQUARE_TOLERANCE,
    )
    thickness_unchanged = _within_abs(
        bbox_edited["z_len"],
        bbox_original["z_len"],
        THICKNESS_TOLERANCE,
    )
    return y_increased_correctly and is_square and thickness_unchanged


def _location_ok(slab_original, slab_edited):
    bbox_original = _bbox_in_meters(slab_original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(slab_edited, UNIT_SCALE)

    return (
        _within_abs(
            bbox_edited["x_center"],
            bbox_original["x_center"],
            CENTER_TOLERANCE,
        )
        and _within_abs(
            bbox_edited["y_center"],
            bbox_original["y_center"],
            CENTER_TOLERANCE,
        )
        and _within_abs(
            bbox_edited["z_center"],
            bbox_original["z_center"],
            CENTER_TOLERANCE,
        )
    )


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

    slab_original = _safe_by_guid(ifc_original, SLAB_GUID)
    slab_edited = _safe_by_guid(ifc_edited, SLAB_GUID)
    if slab_original is None or slab_edited is None:
        return metrics

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[SLAB_GUID],
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        metrics["right_dimensions"] = _dimensions_ok(slab_original, slab_edited)
        metrics["right_location"] = _location_ok(slab_original, slab_edited)
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "01" / "01_01_014.ifc"
    edited_ifc_file = data_dir / "solutions" / "geometry_14.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
