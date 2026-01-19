import ifcopenshell


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the opening with id 0APGbZXNKfgPNB$VQQZ0pi."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False # the opening contains a window. that should also be removed
    }

    edited_ifc = ifcopenshell.open(edited_ifc_file)

    try:
        edited_ifc.by_guid("0APGbZXNKfgPNB$VQQZ0pi")
        # opening is still there -> failed
        return metrics
    except RuntimeError:
        # object does not exist
        metrics["object_not_exists"] = True

    try:
        edited_ifc.by_guid("11kJIqz$n2Jf_DfJV1SDbS")
    except RuntimeError:
        # window also deleted
        metrics["integrity_constraint"] = True

    return metrics