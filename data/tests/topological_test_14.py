import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Trim the beams so that it touches the wall with the id "1A1LNnHqHFQwR1jv6PQkyv"

    Checks:
      - right_dimensions: all beams in the edited IFC have Z-length (ExtrudedAreaSolid.Depth
        or fallback OverallLength) equal to 4600mm (within tolerance).
      - right_location: True iff each beam's placement has NOT changed between original and edited IFC
        (compares IfcLocalPlacement chain: location + axis + refdirection, recursively).
      - integrity_constraint: True iff right_dimensions and right_location are True.
    """
    TARGET_Z = 4600.0
    TOLERANCE = 0.1

    metrics = {
        "right_dimensions": False,
        "right_location": False,
        "integrity_constraint": False,
    }

    f_orig = ifcopenshell.open(ifc_file)
    f_edit = ifcopenshell.open(edited_ifc_file)

    orig_beams = {b.GlobalId: b for b in f_orig.by_type("IfcBeam") if getattr(b, "GlobalId", None)}
    edit_beams = {b.GlobalId: b for b in f_edit.by_type("IfcBeam") if getattr(b, "GlobalId", None)}

    # Need at least one beam, and every edited beam must exist in original for location comparison
    if not edit_beams:
        return metrics
    if not set(edit_beams.keys()).issubset(set(orig_beams.keys())):
        return metrics

    def vec3_from_cartesian_point(p):
        if not p or not getattr(p, "Coordinates", None):
            return None
        coords = list(p.Coordinates)
        # pad to 3
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
        Create a comparable signature of an IfcLocalPlacement chain:
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
            # 2D placement: treat as (x,y,0) and directions padded
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

    def get_extruded_depths_from_item(item):
        depths = []
        if not item or not hasattr(item, "is_a"):
            return depths

        if item.is_a("IfcExtrudedAreaSolid"):
            if hasattr(item, "Depth") and item.Depth is not None:
                depths.append(float(item.Depth))
            return depths

        if item.is_a("IfcMappedItem"):
            mapped_rep = item.MappingSource.MappedRepresentation
            for mi in (mapped_rep.Items or []):
                depths.extend(get_extruded_depths_from_item(mi))
            return depths

        return depths

    # --- right_location: placement unchanged for each edited beam (by GlobalId) ---
    for gid, b_edit in edit_beams.items():
        b_orig = orig_beams[gid]

        sig_orig = placement_signature(getattr(b_orig, "ObjectPlacement", None))
        sig_edit = placement_signature(getattr(b_edit, "ObjectPlacement", None))

        if not signatures_equal(sig_orig, sig_edit, TOLERANCE):
            return metrics

    metrics["right_location"] = True

    # --- right_dimensions: all edited beams have the target depth/length ---
    for beam in edit_beams.values():
        rep = getattr(beam, "Representation", None)

        depths = []
        if rep and getattr(rep, "Representations", None):
            for rep_sub in (rep.Representations or []):
                for item in (rep_sub.Items or []):
                    depths.extend(get_extruded_depths_from_item(item))

        if depths:
            if not all(abs(d - TARGET_Z) <= TOLERANCE for d in depths):
                return metrics
        else:
            if not hasattr(beam, "OverallLength"):
                return metrics
            if beam.OverallLength is None or abs(float(beam.OverallLength) - TARGET_Z) > TOLERANCE:
                return metrics

    metrics["right_dimensions"] = True
    metrics["integrity_constraint"] = metrics["right_dimensions"] and metrics["right_location"]
    return metrics

