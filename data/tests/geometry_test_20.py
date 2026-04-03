import ifcopenshell

from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

COLUMN_GUID = "0lwZAgQMb7yAIJTmmcGlwc"

# Expected correct answer
CORRECT_WALL_GUID = "0lwZAgQMb7yAIJTmmcGloi"

def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: delete the wall closest to the given column (by midpoint-to-wall-edge distance)."""

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

    column_exists = _safe_by_guid(ifc_edited, COLUMN_GUID) is not None
    
    if not column_exists:
        return metrics

    wall_deleted = _safe_by_guid(ifc_edited, CORRECT_WALL_GUID) is None

    if wall_deleted:
        metrics["object_not_exists"] = True
    
    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, [CORRECT_WALL_GUID])

    return metrics
