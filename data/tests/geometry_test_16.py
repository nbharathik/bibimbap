import ifcopenshell


DELETED_DOOR_GUID = "1g0NIEjcH1lfGqbYWRqt6L"
DELETED_OPENING_GUID = "0GJ5vHxGEC4l1pTWzlPYoU"


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
        "door_deleted": False,
        "opening_deleted": False,
    }

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    # 1) Door is deleted
    edited_deleted = _safe_by_guid(ifc_edited, DELETED_DOOR_GUID)
    metrics["door_deleted"] = edited_deleted is None

    # 2) Opening is deleted
    metrics["opening_deleted"] = _safe_by_guid(ifc_edited, DELETED_OPENING_GUID) is None

    return metrics
