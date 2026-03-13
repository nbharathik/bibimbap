import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a slab with dimensions of 10 by 5 meters and the width of 20 centimeters with its bottom and center in (-30, 0)."""
    metrics = {
        "object_exists": False, # slab was created
        "right_location": False, # slab has its center in (-30, 0)
        "right_dimensions": False, # slab has size 10x5x0.2
        "integrity_constraint": False # slab is an IfcSlab
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new slab
    original_slab_guids = set(slab.GlobalId for slab in ifc_original.by_type("IfcSlab"))
    edited_slab_guids = set(slab.GlobalId for slab in ifc_edited.by_type("IfcSlab"))

    new_slab_ids = list(edited_slab_guids - original_slab_guids)
    if len(new_slab_ids) == 0:
        return metrics
    metrics["object_exists"] = True
    slab = ifc_edited.by_guid(new_slab_ids[0])

    # get slab geometry information
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, slab)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_slab = min(vertices[:, 0])
    x_max_slab = max(vertices[:, 0])
    y_min_slab = min(vertices[:, 1])
    y_max_slab = max(vertices[:, 1])
    z_min_slab = min(vertices[:, 2])
    z_max_slab = max(vertices[:, 2])

    width_slab = ifcopenshell.util.shape.get_x(geom)
    height_slab = ifcopenshell.util.shape.get_z(geom)
    thickness_slab = ifcopenshell.util.shape.get_y(geom)


    if ((width_slab == 10.0 and thickness_slab == 5.0) or (width_slab == 5.0 and thickness_slab == 10.0)) and (height_slab == 0.2):
        metrics["right_dimensions"] = True


    if x_min_slab + width_slab/2 == -30.0 and y_min_slab + thickness_slab/2 == 0.0:
        metrics["right_location"] = True

    if slab.is_a("IfcSlab"):
        metrics["integrity_constraint"] = True
    return metrics
