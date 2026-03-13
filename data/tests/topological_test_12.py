import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Shorten the length of the wall by 1m that is outside of the walls with ids
    "3Vyqk8cSj8TOuAk6zHUwBs", "3Vyqk8cSj8TOuAk6zHUw89", "3Vyqk8cSj8TOuAk6zHUwMJ",
    "3Vyqk8cSj8TOuAk6zHUwNQ", "3Vyqk8cSj8TOuAk6zHUwAt", "3Vyqk8cSj8TOuAk6zHUwAc"

    Checks that wall GlobalId = "2c8iwp2JP1ox_Asrwk4CZr" still exists,
    that its rectangular profile XDim was reduced by exactly 1000 (mm),
    and that its placement (location/orientation) has NOT changed between files.

    Metrics (returned):
      - right_dimensions: True iff edited_xdim == original_xdim - 1000 for all
        IfcRectangleProfileDef.XDim reachable via representation (direct or via IfcMappedItem).
      - right_location: True iff wall ObjectPlacement is unchanged between original and edited IFC
        (compares IfcLocalPlacement chain: location + axis + refdirection, recursively).
      - integrity_constraint: True iff right_dimensions and right_location are True.
    """
    wall_guid = "2c8iwp2JP1ox_Asrwk4CZr"
    delta = 1000.0
    TOLERANCE = 0.1

    metrics = {
        "right_dimensions": False,
        "right_location": False,
        "integrity_constraint": False,
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

    # ---- placement comparison helpers (right_location) ----
    def vec3_from_cartesian_point(p):
        if not p or not getattr(p, "Coordinates", None):
            return None
        coords = list(p.Coordinates)
        while len(coords) < 3:
            coords.append(0.0)
        return (float(coords[0]), float(coords[1]), float(coords[2]))

    def vec3_from_direction(d):
        if not d or not getattr(d, "DirectionRatios", None):
            return None
        ratios = list(d.DirectionRatios)
        while len(ratios) < 3:
            ratios.append(0.0)
        return (float(ratios[0]), float(ratios[1]), float(ratios[2]))

    def nearly_equal(a, b, tol=TOLERANCE):
        return abs(float(a) - float(b)) <= tol

    def vec_nearly_equal(v1, v2, tol=TOLERANCE):
        if v1 is None and v2 is None:
            return True
        if v1 is None or v2 is None:
            return False
        return all(nearly_equal(x, y, tol) for x, y in zip(v1, v2))

    def placement_signature(local_placement):
        """
        Comparable signature of an IfcLocalPlacement chain:
        (Location(x,y,z), Axis(dx,dy,dz), RefDirection(rx,ry,rz), parent_signature)
        """
        if local_placement is None or not hasattr(local_placement, "is_a") or not local_placement.is_a("IfcLocalPlacement"):
            return None

        rel = getattr(local_placement, "RelativePlacement", None)
        loc = axis = ref = None

        if rel and rel.is_a("IfcAxis2Placement3D"):
            loc = vec3_from_cartesian_point(getattr(rel, "Location", None))
            axis = vec3_from_direction(getattr(rel, "Axis", None))
            ref = vec3_from_direction(getattr(rel, "RefDirection", None))
        elif rel and rel.is_a("IfcAxis2Placement2D"):
            loc2 = vec3_from_cartesian_point(getattr(rel, "Location", None))
            if loc2 is not None:
                loc = (loc2[0], loc2[1], 0.0)
            ref2 = vec3_from_direction(getattr(rel, "RefDirection", None))
            if ref2 is not None:
                ref = (ref2[0], ref2[1], 0.0)

        parent = getattr(local_placement, "PlacementRelTo", None)
        return (loc, axis, ref, placement_signature(parent))

    def signatures_equal(sig1, sig2, tol=TOLERANCE):
        if sig1 is None and sig2 is None:
            return True
        if sig1 is None or sig2 is None:
            return False

        loc1, axis1, ref1, parent1 = sig1
        loc2, axis2, ref2, parent2 = sig2

        if not vec_nearly_equal(loc1, loc2, tol):
            return False
        if not vec_nearly_equal(axis1, axis2, tol):
            return False
        if not vec_nearly_equal(ref1, ref2, tol):
            return False
        return signatures_equal(parent1, parent2, tol)

    orig_wall = find_wall(ifc_original)
    edit_wall = find_wall(ifc_edited)

    # Require wall to exist in both files (implicit object_exists gate)
    if orig_wall is None or edit_wall is None:
        return metrics

    # ---- right_location ----
    sig_orig = placement_signature(getattr(orig_wall, "ObjectPlacement", None))
    sig_edit = placement_signature(getattr(edit_wall, "ObjectPlacement", None))
    if not signatures_equal(sig_orig, sig_edit, TOLERANCE):
        return metrics
    metrics["right_location"] = True

    # ---- right_dimensions ----
    orig_xdims = collect_xdims_from_wall(orig_wall)
    edit_xdims = collect_xdims_from_wall(edit_wall)

    if not orig_xdims or not edit_xdims:
        return metrics
    if len(orig_xdims) != len(edit_xdims):
        return metrics

    for ox, ex in zip(orig_xdims, edit_xdims):
        if abs(ex - (ox - delta)) > TOLERANCE:
            return metrics

    metrics["right_dimensions"] = True
    metrics["integrity_constraint"] = metrics["right_dimensions"] and metrics["right_location"]
    return metrics


