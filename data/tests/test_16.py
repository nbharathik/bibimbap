import ifcopenshell


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the column with the id 22hyxvAPr65PFt9WZfHS2x."""
    metrics = {
        "object_not_exists": False
    }

    edited_ifc = ifcopenshell.open(edited_ifc_file)

    try:
        edited_ifc.by_guid("22hyxvAPr65PFt9WZfHS2x")
    except RuntimeError:
        # object does not exist
        metrics["object_not_exists"] = True

    return metrics