import ifcopenshell
from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

def _is_deleted(guid, edited_ifc):
    try:
        edited_ifc.by_guid(guid)
        return False
    except RuntimeError:
        return True

column_guids = [
    "0dc_dU7Cj6aRLiY5JtJ$t0",
    "0dc_dU7Cj6aRLiY5JtJ$qt",
    "0Ub9$WlTH44eNTzbw3KFF4",
    "251vDGWZj4fBEsYpTPQwFu"
]

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the columns that are outside of the rooms with global ids 08usg60IH8OxdvepHCDp6f, 08usg60IH8OxdvepHCDp6c."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    if non_target_elements_unchanged(ifcopenshell.open(ifc_file), ifcopenshell.open(edited_ifc_file)): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics


    original_ifc = ifcopenshell.open(ifc_file)
    relationship_ids = {}

    for column_guid in column_guids:
        relationship_ids[column_guid] = []
        column = original_ifc.by_guid(column_guid)

        for rel in original_ifc.get_inverse(column):
            if rel.is_a("IfcRelContainedInSpatialStructure"):
                # these relationships need to be deleted when one of the spaces is deleted
                relationship_ids[column_guid].append(rel.GlobalId)

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, column_guids)

    return metrics
