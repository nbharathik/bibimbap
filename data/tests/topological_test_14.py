import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Trim the beams so that it touches the wall widh the id "1A1LNnHqHFQwR1jv6PQkyv"
    Checks that all beams in the edited IFC have Z-length set EXACTLY to 4600 (mm).
    """
    TARGET_Z = 4600.0

    metrics = {"correct_placement": False}

    f = ifcopenshell.open(edited_ifc_file)
    beams = f.by_type("IfcBeam")

    def get_extruded_depths_from_item(item):
        depths = []
        if item.is_a("IfcExtrudedAreaSolid"):
            if hasattr(item, "Depth") and item.Depth is not None:
                depths.append(float(item.Depth))
        elif item.is_a("IfcMappedItem"):
            mapped_rep = item.MappingSource.MappedRepresentation
            for mi in (mapped_rep.Items or []):
                depths.extend(get_extruded_depths_from_item(mi))
        return depths

    for beam in beams:
        rep = getattr(beam, "Representation", None)

        depths = []
        if rep:
            for rep_sub in (rep.Representations or []):
                for item in (rep_sub.Items or []):
                    depths.extend(get_extruded_depths_from_item(item))

        if depths:
            if not all(d == TARGET_Z for d in depths):
                return metrics
        else:
            if not hasattr(beam, "OverallLength"):
                return metrics
            if beam.OverallLength is None or float(beam.OverallLength) != TARGET_Z:
                return metrics

    metrics["correct_placement"] = True
    return metrics

