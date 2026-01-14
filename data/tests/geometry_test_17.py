import ifcopenshell


WALL_GUIDS = [
    "1u4oG4Ltr15fMWjwJ4pN4F",
    "1u4oG4Ltr15fMWjwJ4pNPJ",
    "1u4oG4Ltr15fMWjwJ4pNUQ",
]


def _exists(ifc, guid: str) -> bool:
    try:
        return ifc.by_guid(guid) is not None
    except Exception:
        return False


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: remove exterior walls separated from the main structure (ground floor).

    Simple check: all specified wall GUIDs are absent in the edited IFC.
    """

    metrics = {f"deleted_{i+1}": False for i in range(len(WALL_GUIDS))}

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    for idx, guid in enumerate(WALL_GUIDS):
        metrics[f"deleted_{idx+1}"] = not _exists(ifc_edited, guid)

    return metrics
