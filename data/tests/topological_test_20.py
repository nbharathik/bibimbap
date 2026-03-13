import ifcopenshell


def _is_deleted(guid, edited_ifc):
    try:
        edited_ifc.by_guid(guid)
        return False
    except RuntimeError:
        return True

column_guids = [
    "0dc_dU7Cj6aRLiY5JtJ$t0",
    "0dc_dU7Cj6aRLiY5JtJ$qt",
    "0Ub9$WlTH44eNTzbw3KFF4",
    "251vDGWZj4fBEsYpTPQwFu"
]

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Delete the columns that are outside of the rooms with global ids 08usg60IH8OxdvepHCDp6f, 08usg60IH8OxdvepHCDp6c."""
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False
    }

    original_ifc = ifcopenshell.open(ifc_file)
    relationship_ids = {}

    for column_guid in column_guids:
        relationship_ids[column_guid] = []
        column = original_ifc.by_guid(column_guid)

        for rel in original_ifc.get_inverse(column):
            if rel.is_a("IfcRelContainedInSpatialStructure"):
                # these relationships need to be deleted when one of the spaces is deleted
                relationship_ids[column_guid].append(rel.GlobalId)

    # now we have the relationships of the space that will be deleted

    edited_ifc = ifcopenshell.open(edited_ifc_file)
    for column_guid in column_guids:
        if not _is_deleted(column_guid, edited_ifc):
            # one of the columns is not deleted -> deleting failed
            return metrics

    # no return in above loop -> every column deleted
    metrics["object_not_exists"] = True

    for column_guid in column_guids:
        for rel_id in relationship_ids[column_guid]:
            if not _is_deleted(rel_id, edited_ifc):
                # one of the relationships still exists -> integrity failed
                return metrics

    # no return in above loop -> every relationship was also deleted
    metrics["integrity_constraint"] = True

    return metrics
