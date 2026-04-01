from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


TARGET_GUIDS = [
    "2KbOAL4v52mv2YJ6fTql5D",
    "2KbOAL4v52mv2YJ6fTql5C",
    "2KbOAL4v52mv2YJ6fTql5F",
    "2KbOAL4v52mv2YJ6fTql5A",
    "2FgYNxuD5JBSJ92imotdSQ",
]

UNIT_SCALE = 1.0
EXPECTED_X_MOVEMENT = 3.0
MOVEMENT_TOLERANCE = 0.1
DIMENSION_TOLERANCE = 0.05


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


def _get_target_pairs(ifc_original, ifc_edited):
    target_pairs = []
    for guid in TARGET_GUIDS:
        original = _safe_by_guid(ifc_original, guid)
        edited = _safe_by_guid(ifc_edited, guid)
        if original is None or edited is None:
            return None
        target_pairs.append((original, edited))
    return target_pairs


def _location_ok(original, edited):
    bbox_original = _bbox_in_meters(original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(edited, UNIT_SCALE)

    return (
        _within_abs(
            bbox_edited["x_center"] - bbox_original["x_center"],
            EXPECTED_X_MOVEMENT,
            MOVEMENT_TOLERANCE,
        )
        and _within_abs(
            bbox_edited["y_center"] - bbox_original["y_center"],
            0.0,
            MOVEMENT_TOLERANCE,
        )
        and _within_abs(
            bbox_edited["z_center"] - bbox_original["z_center"],
            0.0,
            MOVEMENT_TOLERANCE,
        )
    )


def _dimensions_ok(original, edited):
    bbox_original = _bbox_in_meters(original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(edited, UNIT_SCALE)

    return (
        _within_abs(
            bbox_edited["x_len"],
            bbox_original["x_len"],
            DIMENSION_TOLERANCE,
        )
        and _within_abs(
            bbox_edited["y_len"],
            bbox_original["y_len"],
            DIMENSION_TOLERANCE,
        )
        and _within_abs(
            bbox_edited["z_len"],
            bbox_original["z_len"],
            DIMENSION_TOLERANCE,
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

    target_pairs = _get_target_pairs(ifc_original, ifc_edited)
    if target_pairs is None:
        return metrics

    location_results = []
    dimension_results = []
    for original, edited in target_pairs:
        try:
            location_results.append(_location_ok(original, edited))
            dimension_results.append(_dimensions_ok(original, edited))
        except Exception:
            location_results.append(False)
            dimension_results.append(False)

    metrics["right_location"] = all(location_results)
    metrics["right_dimensions"] = all(dimension_results)
    metrics["integrity_constraint"] = bool(check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=TARGET_GUIDS,
    ).get("integrity_constraint", False))
    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "01" / "01_01_013.ifc"
    edited_ifc_file = data_dir / "solutions" / "geometry_13.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
