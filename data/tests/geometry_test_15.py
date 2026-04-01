from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


COLUMN_GUIDS = [
    "3lOEkLxYb9$uRd50gnIDtk",
    "3lOEkLxYb9$uRd50gnIDtl",
    "3lOEkLxYb9$uRd50gnIDpA",
    "3lOEkLxYb9$uRd50gnIDqu",
]

UNIT_SCALE = 1.0
POSITION_TOLERANCE = 0.05
RECTANGLE_TOLERANCE = 0.3
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
    pairs = []
    for guid in COLUMN_GUIDS:
        original = _safe_by_guid(ifc_original, guid)
        edited = _safe_by_guid(ifc_edited, guid)
        if original is None or edited is None:
            return None
        pairs.append((original, edited))
    return pairs


def _cluster_unique(values, tolerance):
    unique_values = []
    for value in sorted(values):
        if not unique_values or abs(value - unique_values[-1]) > tolerance:
            unique_values.append(value)
    return unique_values


def _forms_rectangle(centers):
    x_unique = _cluster_unique([center[0] for center in centers], RECTANGLE_TOLERANCE)
    y_unique = _cluster_unique([center[1] for center in centers], RECTANGLE_TOLERANCE)
    if len(x_unique) != 2 or len(y_unique) != 2:
        return False

    expected_centers = {(x, y) for x in x_unique for y in y_unique}
    for center in centers:
        if not any(
            _within_abs(center[0], expected[0], RECTANGLE_TOLERANCE)
            and _within_abs(center[1], expected[1], RECTANGLE_TOLERANCE)
            for expected in expected_centers
        ):
            return False
    return True


def _dimensions_ok(original, edited):
    bbox_original = _bbox_in_meters(original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(edited, UNIT_SCALE)
    return (
        _within_abs(bbox_edited["x_len"], bbox_original["x_len"], DIMENSION_TOLERANCE)
        and _within_abs(bbox_edited["y_len"], bbox_original["y_len"], DIMENSION_TOLERANCE)
        and _within_abs(bbox_edited["z_len"], bbox_original["z_len"], DIMENSION_TOLERANCE)
    )


def _movement_vector(original, edited):
    bbox_original = _bbox_in_meters(original, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(edited, UNIT_SCALE)
    return (
        bbox_edited["x_center"] - bbox_original["x_center"],
        bbox_edited["y_center"] - bbox_original["y_center"],
        bbox_edited["z_center"] - bbox_original["z_center"],
    )


def _right_location(pairs):
    edited_centers = []
    moved_count = 0

    for original, edited in pairs:
        bbox_edited = _bbox_in_meters(edited, UNIT_SCALE)
        edited_centers.append((bbox_edited["x_center"], bbox_edited["y_center"]))

        dx, dy, dz = _movement_vector(original, edited)
        if (
            abs(dx) > POSITION_TOLERANCE
            or abs(dy) > POSITION_TOLERANCE
            or abs(dz) > POSITION_TOLERANCE
        ):
            moved_count += 1

    return _forms_rectangle(edited_centers) and moved_count == 1


def execute_test(ifc_file, edited_ifc_file, model_output):
    del model_output

    metrics = {
        "right_dimensions": False,
        "integrity_constraint": False,
        "right_location": False,
    }

    ifc_original, ifc_edited = _load_models(ifc_file, edited_ifc_file)
    if ifc_original is None or ifc_edited is None:
        return metrics

    pairs = _get_target_pairs(ifc_original, ifc_edited)
    if pairs is None:
        return metrics

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=COLUMN_GUIDS,
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        metrics["right_dimensions"] = all(
            _dimensions_ok(original, edited) for original, edited in pairs
        )
        metrics["right_location"] = _right_location(pairs)
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "01" / "01_01_015.ifc"
    edited_ifc_file = data_dir / "solutions" / "geometry_15.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
