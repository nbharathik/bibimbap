import ifcopenshell


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Remove the door with id 11kJIqz$n2Jf_DfJV1SDY7."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    edited_ifc = ifcopenshell.open(edited_ifc_file)

    try:
        edited_ifc.by_guid("11kJIqz$n2Jf_DfJV1SDY7")
        # door is still there -> failed
        return metrics
    except RuntimeError:
        # object does not exist
        metrics["object_not_exists"] = True

    try:
        edited_ifc.by_guid("1U$$kq6emLyOkmIlVkRzzn")
    except RuntimeError:
        # opening also deleted
        metrics["integrity_constraint"] = True

    return metrics