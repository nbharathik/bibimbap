import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Change the height of all columns so that they touch the slab with id "0dxtXCDSn2mfP92h$AiPMM"

    Checks that BOTH columns have their Z dimension (IfcExtrudedAreaSolid.Depth)
    set to 2695 (mm), and that their location (placement) has not changed between
    original and edited IFC.

    Metrics (returned):
      - right_dimensions: True iff all reachable IfcExtrudedAreaSolid.Depth values
        (direct or via IfcMappedItem) equal 2695.0 (within tolerance) for BOTH columns
      - right_location: True iff each column's ObjectPlacement is unchanged between
        original and edited IFC (compares IfcLocalPlacement chain)
      - integrity_constraint: True iff right_dimensions and right_location are True
    """
    target_guids = {"0n4qMSuxfEFA0BeEfapSQB", "0n4qMSuxfEFA0BeEfapSHZ"}
    target_z = 2695.0
    TOLERANCE = 0.1

    metrics = {
        "right_dimensions": False,
        "right_location": False,
        "integrity_constraint": False,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def columns_by_guid(model):
        return {
            getattr(c, "GlobalId", None): c
            for c in model.by_type("IfcColumn")
            if getattr(c, "GlobalId", None)
        }

    orig_cols = columns_by_guid(ifc_original)
    edit_cols = columns_by_guid(ifc_edited)

    # Require both columns to exist in both files (implicit "object_exists" gate)
    if not target_guids.issubset(orig_cols.keys()) or not target_guids.issubset(edit_cols.keys()):
        return metrics

    def collect_depths_from_representation(rep):
        depths = []

        def walk_item(item):
            if not item or not hasattr(item, "is_a"):
                return

            if item.is_a("IfcMappedItem"):
                mapped_rep = item.MappingSource.MappedRepresentation
                for mi in (mapped_rep.Items or []):
                    walk_item(mi)
                return

            if item.is_a("IfcExtrudedAreaSolid"):
                if getattr(item, "Depth", None) is not None:
                    depths.append(float(item.Depth))
                return

        if rep and getattr(rep, "Representations", None):
            for rep_sub in (rep.Representations or []):
                for item in (rep_sub.Items or []):
                    walk_item(item)

        return depths

    # ---- right_dimensions ----
    for gid in target_guids:
        col = edit_cols[gid]
        rep = getattr(col, "Representation", None)
        depths = collect_depths_from_representation(rep)

        if not depths:
            return metrics
        if not all(abs(d - target_z) <= TOLERANCE for d in depths):
            return metrics

    metrics["right_dimensions"] = True

    # ---- right_location (unchanged placement vs original) ----
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

    for gid in target_guids:
        orig_col = orig_cols[gid]
        edit_col = edit_cols[gid]

        sig_orig = placement_signature(getattr(orig_col, "ObjectPlacement", None))
        sig_edit = placement_signature(getattr(edit_col, "ObjectPlacement", None))

        if not signatures_equal(sig_orig, sig_edit, TOLERANCE):
            return metrics

    metrics["right_location"] = True

    metrics["integrity_constraint"] = metrics["right_dimensions"] and metrics["right_location"]
    return metrics


