import ifcopenshell


WINDOW_GUIDS = [
    # Window group 1
    "1xzI3PuNvF1RRUjZb8YIP1",
    "1xzI3PuNvF1RRUjZb8YIP0",
    "1xzI3PuNvF1RRUjZb8YIUz",
    # Window group 2
    "1xzI3PuNvF1RRUjZb8YINv",
    "1xzI3PuNvF1RRUjZb8YINr",
    "1xzI3PuNvF1RRUjZb8YINu",
]


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: take out the windows that are in the west walls.

    Simple check: all specified window GUIDs are absent in the edited IFC.

    Note: This test does not attempt to infer "west wall" via geometry; it uses the
    provided ground-truth GUIDs.
    """

    metrics = {f"deleted_{i+1}": False for i in range(len(WINDOW_GUIDS))}

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    for idx, guid in enumerate(WINDOW_GUIDS):
        metrics[f"deleted_{idx+1}"] = _safe_by_guid(ifc_edited, guid) is None

    return metrics
