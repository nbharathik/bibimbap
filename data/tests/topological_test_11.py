"change	the height of all columns so that they touch the slab with id <id>"
import ifcopenshell

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Change the height of all columns so that they touch the slab with id "0dxtXCDSn2mfP92h$AiPMM"

    Checks that BOTH columns have their Z dimension (IfcExtrudedAreaSolid.Depth)
    set EXACTLY to 2695 (mm).

    Metrics:
      - object_exists: both columns exist in both original and edited IFC as IfcColumn
      - correct_dimension: for each column, all reachable IfcExtrudedAreaSolid.Depth
        values (direct or via IfcMappedItem) equal 2695.0 exactly
    """
    target_guids = {"0n4qMSuxfEFA0BeEfapSQB", "0n4qMSuxfEFA0BeEfapSHZ"}
    target_z = 2695.0

    metrics = {
        "object_exists": False,
        "correct_dimension": False,
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

    if not target_guids.issubset(orig_cols.keys()) or not target_guids.issubset(edit_cols.keys()):
        return metrics

    metrics["object_exists"] = True

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

    for gid in target_guids:
        col = edit_cols[gid]
        rep = getattr(col, "Representation", None)
        depths = collect_depths_from_representation(rep)

        # Must be verifiable, and all depths must match exactly
        if not depths:
            return metrics
        if not all(d == target_z for d in depths):
            return metrics

    metrics["correct_dimension"] = True
    return metrics