import ifcopenshell


WINDOW_GUIDS = [
    # Window 1 (provided answer IDs)
    "1mRYVM4YfFFBRkcbz1hH$F",
    "1mRYVM4YfFFBRkcbz1hH$2",
    "1mRYVM4YfFFBRkcbz1hHbM",
    # Window 2 (provided answer IDs)
    "1mRYVM4YfFFBRkcbz1hH_L",
    "1mRYVM4YfFFBRkcbz1hH_M",
    "1mRYVM4YfFFBRkcbz1hH_H",
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

    metrics = {f"deleted_{i+1}": False for i in range(len(WINDOW_GUIDS))}

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    for idx, guid in enumerate(WINDOW_GUIDS):
        metrics[f"deleted_{idx+1}"] = _safe_by_guid(ifc_edited, guid) is None

    return metrics
