import ifcopenshell
import ifcopenshell.util.placement

def execute_test(ifc_file, edited_ifc_file, model_output):
    """
    Change the position of the slab that it lays on the slab with the id "0CJwXarnHAeA7eFXxxI_hO".
    """

    target_guid = "0CJwXarnHAeA7eFXxxI_is" #this is the id of the slab that should be moved
    target_z_mm = 3300.0

    metrics = {
        "object_exists": False,
        "correct_placement": False,
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

    metrics["object_exists"] = True

    def placement_xyz_mm(obj):
        m = ifcopenshell.util.placement.get_local_placement(obj.ObjectPlacement)
        x_m, y_m, z_m = float(m[0][3]), float(m[1][3]), float(m[2][3])
        #print("Placement (m):", x_m, y_m, z_m)
        return x_m, y_m, z_m

    try:
        ox, oy, oz = placement_xyz_mm(orig_obj)
        ex, ey, ez = placement_xyz_mm(edit_obj)
    except Exception:
        return metrics

    z_ok = abs(ez - target_z_mm) == 0
    x_unchanged = abs(ex - ox) == 0
    y_unchanged = abs(ey - oy) == 0

    metrics["correct_placement"] = bool(z_ok and x_unchanged and y_unchanged)
    return metrics