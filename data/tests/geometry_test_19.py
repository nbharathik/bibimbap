import ifcopenshell
from integrity_utils import non_target_elements_unchanged
from delete_integrity import run_delete_integrity_check

WINDOW_GUIDS = [
    "1mRYVM4YfFFBRkcbz1hH$F",
    "1mRYVM4YfFFBRkcbz1hH_L"
]


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: delete the two windows opposite to the referenced wall.

    Simple check: all specified GUIDs are absent in the edited IFC.

    Note: This test uses the provided ground-truth GUIDs and does not attempt to
    infer "opposite to" via geometry.
    """

    metrics = {
        "object_not_exists": False, 
        "integrity_constraint": False,
    }

    if non_target_elements_unchanged(ifc_file, edited_ifc_file): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics


    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    all_deleted = all(
        not _safe_by_guid(ifc_edited, guid) for guid in WINDOW_GUIDS
    )

    metrics["object_not_exists"] = all_deleted
    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, WINDOW_GUIDS)

    return metrics
