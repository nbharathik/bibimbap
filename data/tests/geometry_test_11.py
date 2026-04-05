from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import run_integrity_check


TARGET_GUIDS = [
    "3PQZwOmmD1hgPWgX4XFLJO",
    "3PQZwOmmD1hgPWgX4XFLJP",
    "3PQZwOmmD1hgPWgX4XFLJQ",
    "3PQZwOmmD1hgPWgX4XFLJR",
    "3PQZwOmmD1hgPWgX4XFLJV",
    "3PQZwOmmD1hgPWgX4XFLJU",
]

UNIT_SCALE = 1.0
HEIGHT_REDUCTION = 0.5
HEIGHT_TOLERANCE = 0.05
LOCATION_TOLERANCE = 0.05


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


def _get_target_wall_pairs(ifc_original, ifc_edited):
    wall_pairs = []
    for guid in TARGET_GUIDS:
        wall_original = _safe_by_guid(ifc_original, guid)
        wall_edited = _safe_by_guid(ifc_edited, guid)
        if wall_original is None or wall_edited is None:
            return None
        wall_pairs.append((wall_original, wall_edited))
    return wall_pairs


def _wall_height_and_location_ok(wall_original, wall_edited):
    bbox_original = _bbox_in_meters(wall_original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(wall_edited, UNIT_SCALE)

    height_diff = bbox_original["z_len"] - bbox_edited["z_len"]
    height_ok = _within_abs(height_diff, HEIGHT_REDUCTION, HEIGHT_TOLERANCE)
    location_ok = (
        _within_abs(
            bbox_original["x_center"],
            bbox_edited["x_center"],
            LOCATION_TOLERANCE,
        )
        and _within_abs(
            bbox_original["y_center"],
            bbox_edited["y_center"],
            LOCATION_TOLERANCE,
        )
        and _within_abs(
            bbox_original["z_min"],
            bbox_edited["z_min"],
            LOCATION_TOLERANCE,
        )
    )
    return height_ok, location_ok


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

    wall_pairs = _get_target_wall_pairs(ifc_original, ifc_edited)
    if wall_pairs is None:
        return metrics

    heights_correct = []
    locations_correct = []
    for wall_original, wall_edited in wall_pairs:
        try:
            height_ok, location_ok = _wall_height_and_location_ok(
                wall_original,
                wall_edited,
            )
        except Exception:
            height_ok = False
            location_ok = False

        heights_correct.append(height_ok)
        locations_correct.append(location_ok)

    metrics["right_dimensions"] = all(heights_correct)
    metrics["right_location"] = all(locations_correct)
    metrics["integrity_constraint"] = run_integrity_check(
        ifc_file,
        edited_ifc_file,
        target_guids=TARGET_GUIDS,
    )
    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "01" / "01_01_011.ifc"
    edited_ifc_file = data_dir / "solutions" / "geometry_11.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
