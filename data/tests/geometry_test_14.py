import math
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


SLAB_GUID = "11kJIqz$n2Jf_DfJV1SCVP"


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
        "x_c": (x_min + x_max) / 2.0,
        "y_c": (y_min + y_max) / 2.0,
        "z_c": (z_min + z_max) / 2.0,
    }


def _within_abs(value, expected, tol):
    return abs(value - expected) <= tol


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: increase the length of one side of the slab so that it forms a square

    Expected behavior:
    - The slab with GUID "11kJIqz$n2Jf_DfJV1SCVP" should have one side increased.
    - Originally: one side is 8.5m, the other is 10m.
    - After edit: Y direction should increase by ~1.5m (from 8.5m to 10m).
    - Result: slab should be approximately square (both sides ~10m).

    Metrics:
    - right_dimensions: The slab forms a square shape (x_len ≈ y_len within 0.2m tolerance)
    """

    metrics = {
        "integrity_constraint": False,
        "right_dimensions": False,
        "right_location": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    unit_scale = 1.0
    square_tolerance = 0.2
    y_increase_expected = 1.5
    y_increase_tolerance = 0.2

    slab_original = _safe_by_guid(ifc_original, SLAB_GUID)
    slab_edited = _safe_by_guid(ifc_edited, SLAB_GUID)

    if slab_original is None or slab_edited is None:
        return metrics

    try:
        bbox_original = _bbox_in_meters(slab_original, unit_scale)
        bbox_edited = _bbox_in_meters(slab_edited, unit_scale)
        
        y_increase = bbox_edited["y_len"] - bbox_original["y_len"]
        y_increased_correctly = _within_abs(y_increase, y_increase_expected, y_increase_tolerance)
        
        x_len = bbox_edited["x_len"]
        y_len = bbox_edited["y_len"]
        is_square = abs(x_len - y_len) <= square_tolerance
        
        metrics["right_dimensions"] = y_increased_correctly and is_square
        metrics["integrity_constraint"] = bool(slab_edited.is_a("IfcSlab"))
        metrics["right_location"] = metrics["integrity_constraint"]
        
    except Exception:
        return metrics

    return metrics
