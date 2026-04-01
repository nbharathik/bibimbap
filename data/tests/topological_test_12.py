from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


WALL_GUID = "2c8iwp2JP1ox_Asrwk4CZr"

UNIT_SCALE = 1.0
EXPECTED_REDUCTION = 1.0
LENGTH_TOLERANCE = 0.05
POSITION_TOLERANCE = 0.02
DIMENSION_TOLERANCE = 0.02


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


def _point_signature(point):
    if not point or not getattr(point, "Coordinates", None):
        return None
    coords = list(point.Coordinates)
    while len(coords) < 3:
        coords.append(0.0)
    return tuple(float(value) for value in coords[:3])


def _direction_signature(direction):
    if not direction or not getattr(direction, "DirectionRatios", None):
        return None
    ratios = list(direction.DirectionRatios)
    while len(ratios) < 3:
        ratios.append(0.0)
    return tuple(float(value) for value in ratios[:3])


def _vector_nearly_equal(vector_1, vector_2, tolerance):
    if vector_1 is None and vector_2 is None:
        return True
    if vector_1 is None or vector_2 is None:
        return False
    return all(
        _within_abs(value_1, value_2, tolerance)
        for value_1, value_2 in zip(vector_1, vector_2)
    )


def _placement_signature(local_placement):
    if (
        local_placement is None
        or not hasattr(local_placement, "is_a")
        or not local_placement.is_a("IfcLocalPlacement")
    ):
        return None

    rel = getattr(local_placement, "RelativePlacement", None)
    loc = axis = ref = None
    if rel and rel.is_a("IfcAxis2Placement3D"):
        loc = _point_signature(getattr(rel, "Location", None))
        axis = _direction_signature(getattr(rel, "Axis", None))
        ref = _direction_signature(getattr(rel, "RefDirection", None))
    elif rel and rel.is_a("IfcAxis2Placement2D"):
        loc = _point_signature(getattr(rel, "Location", None))
        ref = _direction_signature(getattr(rel, "RefDirection", None))

    parent = getattr(local_placement, "PlacementRelTo", None)
    return (loc, axis, ref, _placement_signature(parent))


def _placement_signatures_equal(signature_1, signature_2, tolerance):
    if signature_1 is None and signature_2 is None:
        return True
    if signature_1 is None or signature_2 is None:
        return False

    loc_1, axis_1, ref_1, parent_1 = signature_1
    loc_2, axis_2, ref_2, parent_2 = signature_2
    return (
        _vector_nearly_equal(loc_1, loc_2, tolerance)
        and _vector_nearly_equal(axis_1, axis_2, tolerance)
        and _vector_nearly_equal(ref_1, ref_2, tolerance)
        and _placement_signatures_equal(parent_1, parent_2, tolerance)
    )


def _right_dimensions(original_wall, edited_wall):
    bbox_original = _bbox_in_meters(original_wall, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(edited_wall, UNIT_SCALE)

    original_length = max(bbox_original["x_len"], bbox_original["y_len"])
    edited_length = max(bbox_edited["x_len"], bbox_edited["y_len"])
    return _within_abs(
        original_length - edited_length,
        EXPECTED_REDUCTION,
        LENGTH_TOLERANCE,
    )


def _right_location(original_wall, edited_wall):
    bbox_original = _bbox_in_meters(original_wall, UNIT_SCALE)
    bbox_edited = _bbox_in_meters(edited_wall, UNIT_SCALE)

    original_minor = min(bbox_original["x_len"], bbox_original["y_len"])
    edited_minor = min(bbox_edited["x_len"], bbox_edited["y_len"])

    return (
        _within_abs(bbox_edited["x_center"], bbox_original["x_center"], POSITION_TOLERANCE)
        and _within_abs(bbox_edited["y_center"], bbox_original["y_center"], POSITION_TOLERANCE)
        and _within_abs(bbox_edited["z_center"], bbox_original["z_center"], POSITION_TOLERANCE)
        and _within_abs(bbox_edited["z_len"], bbox_original["z_len"], DIMENSION_TOLERANCE)
        and _within_abs(edited_minor, original_minor, DIMENSION_TOLERANCE)
        and _placement_signatures_equal(
            _placement_signature(getattr(original_wall, "ObjectPlacement", None)),
            _placement_signature(getattr(edited_wall, "ObjectPlacement", None)),
            POSITION_TOLERANCE,
        )
    )


def execute_test(ifc_file, edited_ifc_file, model_output):
    del model_output

    metrics = {
        "right_dimensions": False,
        "right_location": False,
        "integrity_constraint": False,
    }

    ifc_original, ifc_edited = _load_models(ifc_file, edited_ifc_file)
    if ifc_original is None or ifc_edited is None:
        return metrics

    original_wall = _safe_by_guid(ifc_original, WALL_GUID)
    edited_wall = _safe_by_guid(ifc_edited, WALL_GUID)
    if original_wall is None or edited_wall is None:
        return metrics

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[WALL_GUID],
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        metrics["right_dimensions"] = _right_dimensions(original_wall, edited_wall)
        metrics["right_location"] = _right_location(original_wall, edited_wall)
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "02" / "01_02_012.ifc"
    edited_ifc_file = data_dir / "solutions" / "topological_12.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
