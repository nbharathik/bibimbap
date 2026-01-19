import ifcopenshell


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Take out the room with id 2UsXAbj6n0fwEWqdkVuHyo."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    original_ifc = ifcopenshell.open(ifc_file)
    original_space = original_ifc.by_guid("2UsXAbj6n0fwEWqdkVuHyo")
    relationship_ids = []
    for rel in original_ifc.get_inverse(original_space):
        if rel.is_a("IfcRelAggregates"):
            # these relationships need to be deleted when one of the spaces is deleted
            relationship_ids.append(rel.GlobalId)

    # now we have the relationships of the space that will be deleted

    edited_ifc = ifcopenshell.open(edited_ifc_file)
    try:
        edited_ifc.by_guid("2UsXAbj6n0fwEWqdkVuHyo")
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

#execute_test("../ifc/basic_tasks.ifc", "../ifc/basic_task_deleted_wall.ifc", {})