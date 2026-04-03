import ifcopenshell

from data.tests.integrity_utils import non_target_elements_unchanged
from data.tests.delete_integrity import run_delete_integrity_check

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the column with the id 22hyxvAPr65PFt9WZfHS2x."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    if non_target_elements_unchanged(ifcopenshell.open(ifc_file), ifcopenshell.open(edited_ifc_file)): # calling this without target elements
        # all elements remained the same -> model did changed nothing -> zero score
        return metrics

    edited_ifc = ifcopenshell.open(edited_ifc_file)

    try:
        edited_ifc.by_guid("22hyxvAPr65PFt9WZfHS2x")
    except RuntimeError:
        # object does not exist
        metrics["object_not_exists"] = True

    metrics["integrity_constraint"] = run_delete_integrity_check(ifc_file, edited_ifc_file, ["22hyxvAPr65PFt9WZfHS2x"])

    return metrics

if __name__ == "__main__":
    execute_test("../ifc/basic_tasks.ifc", "../../results/run_2026-04-03_13-44-28/edited_ifc_claude-opus-4-6/0/basic_tasks_0.ifc", "")