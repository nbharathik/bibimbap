import ifcopenshell

from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the room that is enclosed by the walls with ids 3Vyqk8cSj8TOuAk6zHUwNQ, 3Vyqk8cSj8TOuAk6zHUwAt, 3Vyqk8cSj8TOuAk6zHUwAc, 3Vyqk8cSj8TOuAk6zHUwBs, 3Vyqk8cSj8TOuAk6zHUw89, 3Vyqk8cSj8TOuAk6zHUwIV."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    if non_target_elements_unchanged(ifcopenshell.open(ifc_file), ifcopenshell.open(edited_ifc_file)): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    original_ifc = ifcopenshell.open(ifc_file)
    original_space = original_ifc.by_guid("3Vyqk8cSj8TOuAk6zHUwK5")
    relationship_ids = []
    for rel in original_ifc.get_inverse(original_space):
        if rel.is_a("IfcRelAggregates"):
            # these relationships need to be deleted when one of the spaces is deleted
            relationship_ids.append(rel.GlobalId)

    # now we have the relationships of the space that will be deleted

    edited_ifc = ifcopenshell.open(edited_ifc_file)
    try:
        edited_ifc.by_guid("3Vyqk8cSj8TOuAk6zHUwK5")
        # space is still there -> failed
        return metrics
    except RuntimeError:
        # object does not exist
        metrics["object_not_exists"] = True

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, ["3Vyqk8cSj8TOuAk6zHUwK5"])

    return metrics
