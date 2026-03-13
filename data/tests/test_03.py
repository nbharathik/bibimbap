import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import math

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add an opening of size 5 by 5 meters to the center of the slab with id 11kJIqz$n2Jf_DfJV1SCVP."""
    metrics = {
        "object_exists": False, # opening was created
        "right_location": False, # opening is in center of slab
        "right_dimensions": False, # opening has size 5x5
        "integrity_constraint": False # opening has has voids relationship
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # get slab and geometry information
    slab = ifc_edited.by_guid("11kJIqz$n2Jf_DfJV1SCVP")
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

    # check if there is a new opening
    original_opening_guids = set(opening.GlobalId for opening in ifc_original.by_type("IfcOpeningElement"))
    edited_opening_guids = set(opening.GlobalId for opening in ifc_edited.by_type("IfcOpeningElement"))

    new_opening_ids = list(edited_opening_guids - original_opening_guids)

    if len(new_opening_ids) == 0:
        return metrics

    metrics["object_exists"] = True
    opening = ifc_edited.by_guid(new_opening_ids[0])


    # get geometry information of the new door
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, opening)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_opening = min(vertices[:, 0])
    x_max_opening = max(vertices[:, 0])
    y_min_opening = min(vertices[:, 1])
    y_max_opening = max(vertices[:, 1])
    z_min_opening = min(vertices[:, 2])
    z_max_opening = max(vertices[:, 2])

    width_opening = ifcopenshell.util.shape.get_x(geom)
    thickness_opening = ifcopenshell.util.shape.get_y(geom)

    # check for right size dimensions
    if width_opening == 5.0 and thickness_opening == 5.0:
        metrics["right_dimensions"] = True

    # check for right location (opening in center of slab)
    if metrics["right_dimensions"]:
        # same distance from outside of opening to outside of slab at all edges, ie opening is centered
        if (math.fabs(x_min_slab - x_min_opening) == math.fabs(x_max_slab - x_max_opening)) and (math.fabs(y_min_slab - y_min_opening) == math.fabs(y_max_slab - y_max_opening)):
            # opening is on slab
            if x_min_slab > x_min_opening and x_max_slab < x_max_opening and y_min_slab > y_min_opening and y_max_slab < y_max_opening:
                # opening goes through slab
                if z_min_slab <= z_min_opening and z_max_slab >= z_max_opening:
                    metrics["right_location"] = True


    # get voids relationship of opening and slab and check if they exist and correspond

    opening_voids_relationship = list(filter(lambda x: x.is_a("IfcRelVoidsElement"), ifc_edited.get_inverse(opening)))
    if len(opening_voids_relationship) == 0:
        return metrics
    opening_voids_relationship = opening_voids_relationship[0].GlobalId


    slab_voids_relationship = list(filter(lambda x: x.is_a("IfcRelVoidsElement"), ifc_edited.get_inverse(slab)))
    if len(slab_voids_relationship) == 0:
        return metrics
    slab_voids_relationship = slab_voids_relationship[0].GlobalId


    if opening_voids_relationship != slab_voids_relationship:
        return metrics

    # every integrity constraint true
    metrics["integrity_constraint"] = True

    return metrics
