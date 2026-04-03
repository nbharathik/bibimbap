import ifcopenshell
from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Delete columns that have no relationship with the slab with the id "2IIWDJ6bzEPxU4iXeUX9Z5".
    """

    target_column_guids = {
        "2IIWDJ6bzEPxU4iXeUX9_B",
        "2IIWDJ6bzEPxU4iXeUX9ow",
        "2IIWDJ6bzEPxU4iXeUX9rM",
        "2IIWDJ6bzEPxU4iXeUX9rK",
        "2IIWDJ6bzEPxU4iXeUX9ti",
    }

    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False,
    }

    if non_target_elements_unchanged(ifcopenshell.open(ifc_file), ifcopenshell.open(edited_ifc_file)): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def ids_of_type(model, ifc_type):
        return {
            obj.GlobalId
            for obj in model.by_type(ifc_type)
            if getattr(obj, "GlobalId", None)
        }

    # ---- object_not_exists ----
    orig_column_ids = ids_of_type(ifc_original, "IfcColumn")
    edited_column_ids = ids_of_type(ifc_edited, "IfcColumn")

    existed_in_original = target_column_guids.issubset(orig_column_ids)
    absent_in_edited = target_column_guids.isdisjoint(edited_column_ids)

    metrics["object_not_exists"] = existed_in_original and absent_in_edited

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, target_column_guids)

    return metrics