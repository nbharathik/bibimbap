import ifcopenshell
import ifcopenshell.util.placement

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Change the position of the slab so that it lays on the slab with the id "0CJwXarnHAeA7eFXxxI_hO".
    """

    target_guid = "0CJwXarnHAeA7eFXxxI_is"  # this is the id of the slab that should be moved
    target_z_mm = 3300.0
    TOLERANCE = 0.1

    metrics = {
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    def find_by_guid(model, guid):
        for obj in model.by_type("IfcRoot"):
            if getattr(obj, "GlobalId", None) == guid:
                return obj
        return None

    orig_obj = find_by_guid(ifc_original, target_guid)
    edit_obj = find_by_guid(ifc_edited, target_guid)

    if orig_obj is None or edit_obj is None:
        return metrics


    def placement_xyz_mm(obj):
        m = ifcopenshell.util.placement.get_local_placement(obj.ObjectPlacement)
        x, y, z = float(m[0][3]), float(m[1][3]), float(m[2][3])
        return x, y, z

    try:
        ox, oy, oz = placement_xyz_mm(orig_obj)
        ex, ey, ez = placement_xyz_mm(edit_obj)
    except Exception:
        return metrics

    # Location rule: Z is set to target_z_mm, and X/Y unchanged vs original
    z_ok = abs(ez - target_z_mm) <= TOLERANCE
    x_unchanged = abs(ex - ox) <= TOLERANCE
    y_unchanged = abs(ey - oy) <= TOLERANCE

    metrics["right_location"] = bool(z_ok and x_unchanged and y_unchanged)

    # No dimension change requirement specified for this task, so treat dimensions as OK
    # (kept explicit as a metric for consistency with other tests).
    metrics["right_dimensions"] = True

    metrics["integrity_constraint"] = (
        metrics["right_location"] and metrics["right_dimensions"]
    )
    return metrics

if __name__ == "__main__":
    import sys
    result = execute_test("/Users/tobi/Documents/Projekte/Show2Instruct/bim-benchmark/test_case_files/01/02/01_02_015_new.ifc","/Users/tobi/Documents/Projekte/Show2Instruct/bim-benchmark/test_case_files/01/02/01_02_015_out.ifc" , None)
    print(result)
