import ifcopenshell


DELETED_DOOR_GUID = "1g0NIEjcH1lfGqbYWRqt6L"
DELETED_OPENING_GUID = "0GJ5vHxGEC4l1pTWzlPYoU"

from integrity_utils import non_target_elements_unchanged
from delete_integrity import run_delete_integrity_check

def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: delete the door between two other doors.

    Simple checks only:
    - The door GUID is not present in the edited IFC.
    - The opening GUID is not present in the edited IFC.
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

    # 1) Door is deleted
    edited_deleted = _safe_by_guid(ifc_edited, DELETED_DOOR_GUID)
    metrics["object_not_exists"] = edited_deleted is None

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, [DELETED_DOOR_GUID])
    return metrics
