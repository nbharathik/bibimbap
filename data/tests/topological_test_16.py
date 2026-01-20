import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Remove the wall that touches both the walls with ids 3cmsjRvPb4wf9t15K203w_ and 3cmsjRvPb4wf9t15K203XR.

    Check that a target wall was removed, and that no integrity constraints are violated
    (i.e., no relationships in the edited model still reference the removed wall GUID).

    Metrics:
      - object_removed: target wall exists in original as IfcWall/IfcWallStandardCase and
                       is absent in edited as IfcWall/IfcWallStandardCase.
      - integrity_constraint: in the edited file, no IfcRelationship still references
                              the removed wall GUID (no dangling references).
    """

    target_wall_guid = "3cmsjRvPb4wf9t15K203Cj"

    metrics = {
        "object_removed": False,
        "integrity_constraint": False,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def ids_of_types(model, types):
        out = set()
        for t in types:
            for obj in model.by_type(t):
                gid = getattr(obj, "GlobalId", None)
                if gid:
                    out.add(gid)
        return out

    # ---- object_removed ----
    wall_types = ["IfcWall", "IfcWallStandardCase"]
    orig_wall_ids = ids_of_types(ifc_original, wall_types)
    edited_wall_ids = ids_of_types(ifc_edited, wall_types)

    metrics["object_removed"] = (target_wall_guid in orig_wall_ids) and (target_wall_guid not in edited_wall_ids)

    # ---- integrity_constraint ----
    def contains_guid(value, guid):
        if value is None:
            return False
        if hasattr(value, "is_a"):  # entity instance
            return getattr(value, "GlobalId", None) == guid
        if isinstance(value, (list, tuple)):  # aggregate
            return any(contains_guid(v, guid) for v in value)
        return False

    dangling = False
    try:
        relationships = ifc_edited.by_type("IfcRelationship")
    except Exception:
        relationships = [r for r in ifc_edited.by_type("IfcRoot") if r.is_a().startswith("IfcRel")]

    for rel in relationships:
        info = rel.get_info()
        for k, v in info.items():
            if k in ("id", "type"):
                continue
            if contains_guid(v, target_wall_guid):
                dangling = True
                break
        if dangling:
            break

    metrics["integrity_constraint"] = (not dangling)

    return metrics
