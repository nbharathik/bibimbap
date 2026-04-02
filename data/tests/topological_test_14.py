from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import check_integrity


REFERENCE_WALL_GUID = "1A1LNnHqHFQwR1jv6PQkyv"
UNIT_SCALE = 1.0
TOUCH_TOLERANCE = 0.02
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


def _placement_signature(local_placement):
    if (
        local_placement is None
        or not hasattr(local_placement, "is_a")
        or not local_placement.is_a("IfcLocalPlacement")
    ):
        return None

    relative = getattr(local_placement, "RelativePlacement", None)
    location = axis = ref_direction = None
    if relative and relative.is_a("IfcAxis2Placement3D"):
        location = _point_signature(getattr(relative, "Location", None))
        axis = _direction_signature(getattr(relative, "Axis", None))
        ref_direction = _direction_signature(getattr(relative, "RefDirection", None))
    elif relative and relative.is_a("IfcAxis2Placement2D"):
        location = _point_signature(getattr(relative, "Location", None))
        ref_direction = _direction_signature(getattr(relative, "RefDirection", None))

    parent = getattr(local_placement, "PlacementRelTo", None)
    return (location, axis, ref_direction, _placement_signature(parent))


def _vector_nearly_equal(vector_1, vector_2, tolerance):
    if vector_1 is None and vector_2 is None:
        return True
    if vector_1 is None or vector_2 is None:
        return False
    return all(
        _within_abs(value_1, value_2, tolerance)
        for value_1, value_2 in zip(vector_1, vector_2)
    )


def _placement_signatures_equal(signature_1, signature_2, tolerance):
    if signature_1 is None and signature_2 is None:
        return True
    if signature_1 is None or signature_2 is None:
        return False

    location_1, axis_1, ref_direction_1, parent_1 = signature_1
    location_2, axis_2, ref_direction_2, parent_2 = signature_2
    return (
        _vector_nearly_equal(location_1, location_2, tolerance)
        and _vector_nearly_equal(axis_1, axis_2, tolerance)
        and _vector_nearly_equal(ref_direction_1, ref_direction_2, tolerance)
        and _placement_signatures_equal(parent_1, parent_2, tolerance)
    )


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Trim the beams so that they touch the wall with the id
    "1A1LNnHqHFQwR1jv6PQkyv".

    Expected behavior:
    - All original beams are shortened until their free end reaches the reference wall.
    - Beam placements stay unchanged; only the beam length changes.
    - The rest of the rooted model remains unchanged.

    Metrics:
    - right_dimensions: Every beam ends at the reference wall face.
    - right_location: Every beam keeps its placement and unchanged cross-section/height.
    - integrity_constraint: Only the intended beam targets change and the model stays
      clash-free.
    """
    del model_output

    metrics = {
        "right_dimensions": False,
        "right_location": False,
        "integrity_constraint": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    original_beams = {
        beam.GlobalId: beam
        for beam in ifc_original.by_type("IfcBeam")
        if getattr(beam, "GlobalId", None)
    }
    edited_beams = {
        beam.GlobalId: beam
        for beam in ifc_edited.by_type("IfcBeam")
        if getattr(beam, "GlobalId", None)
    }
    reference_wall = ifc_edited.by_guid(REFERENCE_WALL_GUID)

    if not original_beams or set(original_beams) != set(edited_beams) or reference_wall is None:
        return metrics

    target_guids = sorted(original_beams)
    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=target_guids,
    )
    metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        wall_bbox = _bbox_in_meters(reference_wall, UNIT_SCALE)

        right_dimensions = True
        right_location = True

        for guid in target_guids:
            original_beam = original_beams[guid]
            edited_beam = edited_beams[guid]
            original_bbox = _bbox_in_meters(original_beam, UNIT_SCALE)
            edited_bbox = _bbox_in_meters(edited_beam, UNIT_SCALE)

            # The task-specific topological requirement is that the trimmed beam end
            # lands on the wall face. In this benchmark layout that face is the wall's
            # minimum Y plane.
            if not _within_abs(edited_bbox["y_max"], wall_bbox["y_min"], TOUCH_TOLERANCE):
                right_dimensions = False

            # Trimming should not move the beam placement or alter its section/height.
            if not _placement_signatures_equal(
                _placement_signature(getattr(original_beam, "ObjectPlacement", None)),
                _placement_signature(getattr(edited_beam, "ObjectPlacement", None)),
                POSITION_TOLERANCE,
            ):
                right_location = False

            if not _within_abs(
                edited_bbox["x_center"],
                original_bbox["x_center"],
                POSITION_TOLERANCE,
            ):
                right_location = False
            if not _within_abs(
                edited_bbox["z_center"],
                original_bbox["z_center"],
                POSITION_TOLERANCE,
            ):
                right_location = False
            if not _within_abs(
                edited_bbox["x_len"],
                original_bbox["x_len"],
                DIMENSION_TOLERANCE,
            ):
                right_location = False
            if not _within_abs(
                edited_bbox["z_len"],
                original_bbox["z_len"],
                DIMENSION_TOLERANCE,
            ):
                right_location = False

        metrics["right_dimensions"] = right_dimensions
        metrics["right_location"] = right_location
    except Exception:
        return metrics

    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "02" / "01_02_014.ifc"
    edited_ifc_file = data_dir / "solutions" / "topological_14.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
