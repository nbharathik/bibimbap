import ifcopenshell


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the room that is enclosed by the walls with ids 3Vyqk8cSj8TOuAk6zHUwNQ, 3Vyqk8cSj8TOuAk6zHUwAt, 3Vyqk8cSj8TOuAk6zHUwAc, 3Vyqk8cSj8TOuAk6zHUwBs, 3Vyqk8cSj8TOuAk6zHUw89, 3Vyqk8cSj8TOuAk6zHUwIV."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

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

    for guid in relationship_ids:
        try:
            edited_ifc.by_guid(guid)
            # relationship still there -> integrity violated
            return metrics
        except RuntimeError:
            pass

    # no return in above loop -> every relationship was also deleted
    metrics["integrity_constraint"] = True

    return metrics

#execute_test("../ifc/02/01_02_018.ifc", "../ifc/02/01_02_018.ifc", {})