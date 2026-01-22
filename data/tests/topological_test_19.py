import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Remove column that is inside of the walls with the ids 3Vyqk8cSj8TOuAk6zHUwIV, 3Vyqk8cSj8TOuAk6zHUw89, 3Vyqk8cSj8TOuAk6zHUwMJ, 3Vyqk8cSj8TOuAk6zHUwNQ"""

    target_guid = "251vDGWZj4fBEsYpTPQwFu"

    metrics = {
        "object_not_exists": False,
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

    # ---- object_not_exists ----
    orig_columns = ids_of_type(ifc_original, "IfcColumn")
    edited_columns = ids_of_type(ifc_edited, "IfcColumn")
    metrics["object_not_exists"] = (target_guid in orig_columns) and (target_guid not in edited_columns)

    # ---- integrity_constraint for column deletion ----
    # Integrity rule: no relationship in the edited IFC should still reference the deleted column.
    def contains_guid(value, guid):
        if value is None:
            return False
        # entity instance
        if hasattr(value, "is_a"):
            return getattr(value, "GlobalId", None) == guid
        # aggregate
        if isinstance(value, (list, tuple)):
            return any(contains_guid(v, guid) for v in value)
        return False

    dangling_refs = []

    # Check all relationships (IfcRelationship is a good umbrella; fallback to IfcRel* if needed)
    rels = []
    try:
        rels = ifc_edited.by_type("IfcRelationship")
    except Exception:
        # very old schemas / edge cases
        rels = [r for r in ifc_edited.by_type("IfcRoot") if r.is_a().startswith("IfcRel")]

    for rel in rels:
        info = rel.get_info()
        # scan all attributes for references to target_guid
        for k, v in info.items():
            if k in ("id", "type"):
                continue
            if contains_guid(v, target_guid):
                dangling_refs.append((rel.is_a(), getattr(rel, "GlobalId", None), k))
                break

    metrics["integrity_constraint"] = (len(dangling_refs) == 0)

    return metrics

