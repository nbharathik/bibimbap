import ifcopenshell
from integrity_utils import non_target_elements_unchanged
from delete_integrity import run_delete_integrity_check

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Remove column that is inside of the walls with the ids 3Vyqk8cSj8TOuAk6zHUwIV, 3Vyqk8cSj8TOuAk6zHUw89, 3Vyqk8cSj8TOuAk6zHUwMJ, 3Vyqk8cSj8TOuAk6zHUwNQ"""

    target_guid = "251vDGWZj4fBEsYpTPQwFu"

    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def ids_of_type(model, ifc_type):
        return {
            obj.GlobalId
            for obj in model.by_type(ifc_type)
            if getattr(obj, "GlobalId", None)
        }

    if non_target_elements_unchanged(ifc_file, edited_ifc_file): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    # ---- object_not_exists ----
    orig_columns = ids_of_type(ifc_original, "IfcColumn")
    edited_columns = ids_of_type(ifc_edited, "IfcColumn")
    metrics["object_not_exists"] = (target_guid in orig_columns) and (target_guid not in edited_columns)

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, [target_guid])

    return metrics

