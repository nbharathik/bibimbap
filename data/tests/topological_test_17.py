import ifcopenshell

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
        "object_removed": False,
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

    # ---- object_removed ----
    orig_column_ids = ids_of_type(ifc_original, "IfcColumn")
    edited_column_ids = ids_of_type(ifc_edited, "IfcColumn")

    existed_in_original = target_column_guids.issubset(orig_column_ids)
    absent_in_edited = target_column_guids.isdisjoint(edited_column_ids)

    metrics["object_removed"] = existed_in_original and absent_in_edited

    # ---- integrity_constraint ----
    # No IfcRelationship in the edited model should still reference any removed column GUID.
    def contains_any_guid(value, guid_set):
        if value is None:
            return False
        if hasattr(value, "is_a"):  # entity instance
            gid = getattr(value, "GlobalId", None)
            return gid in guid_set if gid else False
        if isinstance(value, (list, tuple)):  # aggregate
            return any(contains_any_guid(v, guid_set) for v in value)
        return False

    dangling = False
    try:
        relationships = ifc_edited.by_type("IfcRelationship")
    except Exception:
        # Fallback: any IfcRoot whose type starts with IfcRel
        relationships = [r for r in ifc_edited.by_type("IfcRoot") if r.is_a().startswith("IfcRel")]

    for rel in relationships:
        info = rel.get_info()
        for k, v in info.items():
            if k in ("id", "type"):
                continue
            if contains_any_guid(v, target_column_guids):
                dangling = True
                break
        if dangling:
            break

    metrics["integrity_constraint"] = (not dangling)

    return metrics