import ifcopenshell


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Remove the wall with id 2UsXAbj6n0fwEWqdkVuHyn."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    original_ifc = ifcopenshell.open(ifc_file)
    original_wall = original_ifc.by_guid("2UsXAbj6n0fwEWqdkVuHyn")
    relationship_ids = []
    for rel in original_ifc.get_inverse(original_wall):
        if rel.is_a("IfcRelConnectsPathElements"):
            # these relationships need to be deleted when one of the walls is deleted
            relationship_ids.append(rel.GlobalId)

    # now we have the relationships of the wall that will be deleted

    edited_ifc = ifcopenshell.open(edited_ifc_file)
    try:
        edited_ifc.by_guid("2UsXAbj6n0fwEWqdkVuHyn")
        # wall is still there -> failed
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

#execute_test("../ifc/basic_tasks.ifc", "../ifc/basic_task_deleted_wall.ifc", {})