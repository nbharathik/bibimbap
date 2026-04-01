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
from data.updated_tests._integrity_utils import filled_opening_guid


WINDOW_GUID = "11kJIqz$n2Jf_DfJV1SDbS"
OPENING_GUID_FALLBACK = "0APGbZXNKfgPNB$VQQZ0pi"
PROXY_GUID = "11kJIqz$n2Jf_DfJV1SDbO"
PROXY_GUID_2 = "11kJIqz$n2Jf_DfJV1SDbP"
EXPECTED_DELTA_Z_M = 0.5
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


def _moved_up_by_expected_delta(original_product, edited_product):
    original_x, original_y, original_z = _placement_xyz_m(original_product)
    edited_x, edited_y, edited_z = _placement_xyz_m(edited_product)
    return (
        _within_abs(edited_x - original_x, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_y - original_y, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_z - original_z, EXPECTED_DELTA_Z_M, POSITION_TOLERANCE_M)
    )


def _placement_unchanged(original_product, edited_product):
    original_x, original_y, original_z = _placement_xyz_m(original_product)
    edited_x, edited_y, edited_z = _placement_xyz_m(edited_product)
    return (
        _within_abs(edited_x - original_x, 0.0, POSITION_TOLERANCE_M)
        and _within_abs(edited_y - original_y, 0.0, POSITION_TOLERANCE_M)
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


def _height_increased_by_expected_delta(original_product, edited_product):
    original_bbox = _bbox_in_meters(original_product)
    edited_bbox = _bbox_in_meters(edited_product)
    return (
        _within_abs(edited_bbox["x_len"], original_bbox["x_len"], DIMENSION_TOLERANCE_M)
        and _within_abs(edited_bbox["y_len"], original_bbox["y_len"], DIMENSION_TOLERANCE_M)
        and _within_abs(
            edited_bbox["z_len"] - original_bbox["z_len"],
            EXPECTED_DELTA_Z_M,
            DIMENSION_TOLERANCE_M,
        )
    )


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Increase the height by 0.5 meters of the window with id
    11kJIqz$n2Jf_DfJV1SDbS.

    Expected behavior:
    - In this benchmark, two outcomes are accepted:
      1. The complete window assembly is moved up by 0.5 m.
      2. The complete window assembly stays in place and increases in height by 0.5 m.
    - The window, its opening, and the related proxies must all follow the same
      accepted transformation.

    Metrics:
    - right_location: The window assembly either moves up by 0.5 m without X/Y drift
      or stays in place for the resize variant.
    - right_dimensions: The window assembly either keeps the same dimensions for the
      move variant or gains 0.5 m in height for the resize variant.
    - integrity_constraint: Only the window assembly targets change and the model stays
      clash-free.
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

    original_window = _safe_by_guid(ifc_original, WINDOW_GUID)
    edited_window = _safe_by_guid(ifc_edited, WINDOW_GUID)
    opening_guid = filled_opening_guid(ifc_original, WINDOW_GUID) or OPENING_GUID_FALLBACK
    original_opening = _safe_by_guid(ifc_original, opening_guid)
    edited_opening = _safe_by_guid(ifc_edited, opening_guid)
    original_proxy = _safe_by_guid(ifc_original, PROXY_GUID)
    edited_proxy = _safe_by_guid(ifc_edited, PROXY_GUID)
    original_proxy_2 = _safe_by_guid(ifc_original, PROXY_GUID_2)
    edited_proxy_2 = _safe_by_guid(ifc_edited, PROXY_GUID_2)

    if (
        original_window is None
        or edited_window is None
        or original_opening is None
        or edited_opening is None
        or original_proxy is None
        or edited_proxy is None
        or original_proxy_2 is None
        or edited_proxy_2 is None
    ):
        return base_metrics

    # Evaluate integrity independently of task scoring once the files and targets are valid.
    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=[WINDOW_GUID, opening_guid, PROXY_GUID, PROXY_GUID_2],
    )
    base_metrics["integrity_constraint"] = bool(result.get("integrity_constraint", False))

    try:
        # Accept either a pure upward move of the whole assembly or a pure height
        # increase of the whole assembly. Every component has to match the same variant.
        window_move_location_ok = _moved_up_by_expected_delta(original_window, edited_window)
        opening_move_location_ok = _moved_up_by_expected_delta(original_opening, edited_opening)
        proxy_move_location_ok = _moved_up_by_expected_delta(original_proxy, edited_proxy)
        proxy_2_move_location_ok = _moved_up_by_expected_delta(original_proxy_2, edited_proxy_2)
        window_move_dimensions_ok = _dimensions_unchanged(original_window, edited_window)
        opening_move_dimensions_ok = _dimensions_unchanged(original_opening, edited_opening)
        proxy_move_dimensions_ok = _dimensions_unchanged(original_proxy, edited_proxy)
        proxy_2_move_dimensions_ok = _dimensions_unchanged(original_proxy_2, edited_proxy_2)
        base_metrics["right_location"] = (
            window_move_location_ok
            and opening_move_location_ok
            and proxy_move_location_ok
            and proxy_2_move_location_ok
        )
        base_metrics["right_dimensions"] = (
            window_move_dimensions_ok
            and opening_move_dimensions_ok
            and proxy_move_dimensions_ok
            and proxy_2_move_dimensions_ok
        )

        window_resize_location_ok = _placement_unchanged(original_window, edited_window)
        opening_resize_location_ok = _placement_unchanged(original_opening, edited_opening)
        proxy_resize_location_ok = _placement_unchanged(original_proxy, edited_proxy)
        proxy_2_resize_location_ok = _placement_unchanged(original_proxy_2, edited_proxy_2)
        window_resize_dimensions_ok = _height_increased_by_expected_delta(original_window, edited_window)
        opening_resize_dimensions_ok = _height_increased_by_expected_delta(original_opening, edited_opening)
        proxy_resize_dimensions_ok = _height_increased_by_expected_delta(original_proxy, edited_proxy)
        proxy_2_resize_dimensions_ok = _height_increased_by_expected_delta(original_proxy_2, edited_proxy_2)

        resize_variant_location_ok = (
            window_resize_location_ok
            and opening_resize_location_ok
            and proxy_resize_location_ok
            and proxy_2_resize_location_ok
        )
        resize_variant_dimensions_ok = (
            window_resize_dimensions_ok
            and opening_resize_dimensions_ok
            and proxy_resize_dimensions_ok
            and proxy_2_resize_dimensions_ok
        )

        if resize_variant_location_ok and resize_variant_dimensions_ok:
            base_metrics["right_location"] = True
            base_metrics["right_dimensions"] = True
    except Exception:
        return base_metrics

    return base_metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "basic_tasks.ifc"
    edited_ifc_file = data_dir / "solutions" / "test_13.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
