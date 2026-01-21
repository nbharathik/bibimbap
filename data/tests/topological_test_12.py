import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Shorten the length of the wall by 1m that is outside of the walls with ids "3Vyqk8cSj8TOuAk6zHUwBs", "3Vyqk8cSj8TOuAk6zHUw89", "3Vyqk8cSj8TOuAk6zHUwMJ", "3Vyqk8cSj8TOuAk6zHUwNQ", "3Vyqk8cSj8TOuAk6zHUwAt", "3Vyqk8cSj8TOuAk6zHUwAc"
    
    Checks that wall GlobalId = "2c8iwp2JP1ox_Asrwk4CZr" still exists,
    and that its rectangular profile XDim was reduced by exactly 1000 (mm).

    Metrics:
      - object_exists: wall exists in both original and edited IFC
      - correct_dimension: True iff edited_xdim == original_xdim - 1000 for all
        IfcRectangleProfileDef.XDim reachable via the wall's representation
        (direct or via IfcMappedItem). If none found, False.
    """
    
    wall_guid = "2c8iwp2JP1ox_Asrwk4CZr"
    delta = 1000.0

    metrics = {
        "object_exists": False,
        "correct_dimension": False,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def find_wall(model):
        for w in (model.by_type("IfcWall") + model.by_type("IfcWallStandardCase")):
            if getattr(w, "GlobalId", None) == wall_guid:
                return w
        return None

    def collect_xdims_from_wall(wall):
        xdims = []
        rep = getattr(wall, "Representation", None)
        if not rep or not getattr(rep, "Representations", None):
            return xdims

        def walk_item(item):
            if not item or not hasattr(item, "is_a"):
                return

            if item.is_a("IfcMappedItem"):
                mapped_rep = item.MappingSource.MappedRepresentation
                for mi in (mapped_rep.Items or []):
                    walk_item(mi)
                return

            if item.is_a("IfcExtrudedAreaSolid"):
                swept = getattr(item, "SweptArea", None)
                if swept and swept.is_a("IfcRectangleProfileDef"):
                    if swept.XDim is not None:
                        xdims.append(float(swept.XDim))
                return

        for rep_sub in (rep.Representations or []):
            for item in (rep_sub.Items or []):
                walk_item(item)

        return xdims

    orig_wall = find_wall(ifc_original)
    edit_wall = find_wall(ifc_edited)

    if orig_wall is None or edit_wall is None:
        return metrics

    metrics["object_exists"] = True

    orig_xdims = collect_xdims_from_wall(orig_wall)
    edit_xdims = collect_xdims_from_wall(edit_wall)

    if not orig_xdims or not edit_xdims:
        return metrics

    if len(orig_xdims) != len(edit_xdims):
        return metrics

    for ox, ex in zip(orig_xdims, edit_xdims):
        if ex != (ox - delta):
            return metrics

    metrics["correct_dimension"] = True
    return metrics