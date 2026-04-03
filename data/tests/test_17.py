import ifcopenshell

from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Remove the door with id 11kJIqz$n2Jf_DfJV1SDY7."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    if non_target_elements_unchanged(ifc_file, edited_ifc_file): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    edited_ifc = ifcopenshell.open(edited_ifc_file)

    try:
        edited_ifc.by_guid("11kJIqz$n2Jf_DfJV1SDY7")
        # door is still there -> failed
        return metrics
    except RuntimeError:
        # object does not exist
        metrics["object_not_exists"] = True

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, ["11kJIqz$n2Jf_DfJV1SDY7"])

    return metrics