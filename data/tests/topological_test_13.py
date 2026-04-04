from pathlib import Path
import sys

import ifcopenshell
import ifcopenshell.util.placement


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data.tests.integrity_utils import filled_opening_guid, run_integrity_check


WINDOW_GUID = "0HbU4cYqD2SBtSJYoQ_eW1"
TARGET_GLOBAL_Y = 900.0
POSITION_TOLERANCE = 0.1
DIMENSION_TOLERANCE = 0.1


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


def _within_abs(value, expected, tolerance):
    return abs(float(value) - float(expected)) <= tolerance


def _global_y(product):
    placement = getattr(product, "ObjectPlacement", None)
    if placement is None:
        return None
    matrix = ifcopenshell.util.placement.get_local_placement(placement)
    return float(matrix[1][3])


def _find_opening_for_window(ifc_model, window):
    for relation in ifc_model.by_type("IfcRelFillsElement"):
        if relation.RelatedBuildingElement == window:
            return relation.RelatingOpeningElement
    return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Change the position of the window with the id 0HbU4cYqD2SBtSJYoQ_eW1
    so that its inner right side touches the outside of the wall with the id
    0HbU4cYqD2SBtSJYoQ_eXK.

    Expected behavior:
    - The target window is moved to the task-specific Y position implied by the model.
    - The window keeps its OverallWidth and OverallHeight.
    - The filled opening moves together with the window.

    Metrics:
    - right_location: The moved window global Y equals 900.0 within tolerance.
    - right_dimensions: The window width and height remain unchanged.
    - integrity_constraint: The filled opening also reaches global Y = 900.0 and
      the rest of the model stays clash-free.
    """
    del model_output

    metrics = {
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,
    }

    ifc_original, ifc_edited = _load_models(ifc_file, edited_ifc_file)
    if ifc_original is None or ifc_edited is None:
        return metrics

    window_original = _safe_by_guid(ifc_original, WINDOW_GUID)
    window_edited = _safe_by_guid(ifc_edited, WINDOW_GUID)
    if window_original is None or window_edited is None:
        return metrics

    opening_original = _find_opening_for_window(ifc_original, window_original)
    opening_edited = _find_opening_for_window(ifc_edited, window_edited)
    if opening_original is None or opening_edited is None:
        return metrics

    # This task has a single effective target position in the benchmark model,
    # so checking the resulting global Y directly is acceptable and intentional.
    window_y = _global_y(window_edited)
    if window_y is not None and _within_abs(window_y, TARGET_GLOBAL_Y, POSITION_TOLERANCE):
        metrics["right_location"] = True

    # The move should not resize the window; preserve the original authored dimensions.
    width_original = getattr(window_original, "OverallWidth", None)
    height_original = getattr(window_original, "OverallHeight", None)
    width_edited = getattr(window_edited, "OverallWidth", None)
    height_edited = getattr(window_edited, "OverallHeight", None)
    if None not in (width_original, height_original, width_edited, height_edited):
        metrics["right_dimensions"] = (
            _within_abs(width_edited, width_original, DIMENSION_TOLERANCE)
            and _within_abs(height_edited, height_original, DIMENSION_TOLERANCE)
        )

    opening_guid = filled_opening_guid(ifc_original, WINDOW_GUID)
    target_guids = [WINDOW_GUID]
    if opening_guid:
        target_guids.append(opening_guid)

    # Keep the old task-specific assertion: the opening must be moved to the same
    # benchmark position as the window.
    opening_y = _global_y(opening_edited)
    opening_at_target = (
        opening_y is not None
        and _within_abs(opening_y, TARGET_GLOBAL_Y, POSITION_TOLERANCE)
    )

    model_integrity_ok = run_integrity_check(
        ifc_file,
        edited_ifc_file,
        target_guids=target_guids,
    )
    metrics["integrity_constraint"] = opening_at_target and model_integrity_ok
    return metrics


if __name__ == "__main__":
    data_dir = Path(__file__).resolve().parents[1]
    ifc_file = data_dir / "ifc" / "01" / "02" / "01_02_013.ifc"
    edited_ifc_file = data_dir / "solutions" / "topological_13.ifc"
    print(execute_test(str(ifc_file), str(edited_ifc_file), None))
