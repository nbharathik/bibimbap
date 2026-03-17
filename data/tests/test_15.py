import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape


def check_move_y_axis(guid, ifc_file, edited_ifc_file, metrics, ifc_identifier):

    ifc_original = ifcopenshell.open(ifc_file)
    object_to_move = ifc_original.by_guid(guid)

    matrix = ifcopenshell.util.placement.get_local_placement(object_to_move.ObjectPlacement)
    placement_original = matrix[:, 3:][0:3]  # in mm
    x_object_to_move, y_object_to_move, z_object_to_move = list(map(lambda x: x / 1000, placement_original))  # converted to m

    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, object_to_move)
    geom = shape.geometry
    width_object_to_move = ifcopenshell.util.shape.get_x(geom)
    height_object_to_move = ifcopenshell.util.shape.get_z(geom)
    thickness_object_to_move = ifcopenshell.util.shape.get_y(geom)

    ifc_edited = ifcopenshell.open(edited_ifc_file)
    try:
        edited_object = ifc_edited.by_guid(guid)
    except RuntimeError:
        # object to move does not exist in edited file
        # check if there is a new object and use this instead
        original_object_guids = set(object.GlobalId for object in ifc_original.by_type(ifc_identifier))
        edited_object_guids = set(object.GlobalId for object in ifc_edited.by_type(ifc_identifier))
        new_object_ids = list(edited_object_guids - original_object_guids)
        if len(new_object_ids) == 0:
            # original object not existent and no new one? -> task failed
            return metrics
        # new object will be used for tests
        edited_object = ifc_edited.by_guid(new_object_ids[0])

    matrix = ifcopenshell.util.placement.get_local_placement(edited_object.ObjectPlacement)

    placement_edited = matrix[:, 3:][0:3]
    x_object_edited, y_object_edited, z_object_edited = list(map(lambda x: x / 1000, placement_edited))  # converted to m

    # check if object was moved by -3 m in y axis and not in any other axis
    if abs(x_object_edited - x_object_to_move) < 0.1 and abs(y_object_edited - y_object_to_move - 3) < 0.1 and abs(z_object_edited - z_object_to_move) < 0.1:
        metrics["right_location"] = True
    else:
        # if the location is not right, that means simply nothing happened and therefore, the right dimensions does not matter
        return metrics

    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, edited_object)
    geom = shape.geometry
    width_object = ifcopenshell.util.shape.get_x(geom)
    height_object = ifcopenshell.util.shape.get_z(geom)
    thickness_object = ifcopenshell.util.shape.get_y(geom)

    # check if dimensions still the same
    if abs(width_object_to_move - width_object) < 0.1 and abs(thickness_object_to_move - thickness_object) < 0.1 and abs(height_object_to_move - height_object) < 0.1:
        metrics["right_dimensions"] = True

    return metrics


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Move the column eith id 22hyxvAPr65PFt9WZfHSMu by -3 meters in direction of y."""
    metrics = {
        "right_location": False,
        "right_dimensions": False
    }

    door_metrics = check_move_y_axis("22hyxvAPr65PFt9WZfHSMu", ifc_file, edited_ifc_file, {key: False for key in metrics.keys()}, "IfcColumn")

    metrics.update(door_metrics)

    return metrics
