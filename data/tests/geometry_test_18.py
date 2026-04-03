import ifcopenshell

from data.tests.geometry_test_17 import _exists


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


from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

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
    
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False,
    }

    if non_target_elements_unchanged(ifcopenshell.open(ifc_file), ifcopenshell.open(edited_ifc_file)): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics
    
    all_deleted = all(
        not _exists(ifc_edited, guid) for guid in WINDOW_GUIDS
    )

    metrics["object_not_exists"] = all_deleted
    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, WINDOW_GUIDS)
    return metrics
