import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape


def check_move_z_axis(guid, ifc_file, edited_ifc_file, metrics, ifc_identifier):

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

    # check if object was moved by 0.5 m in -z axis and not in any other axis
    if x_object_edited == x_object_to_move and y_object_edited == y_object_to_move and z_object_edited == z_object_to_move - 0.5:
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
    if width_object_to_move == width_object and thickness_object_to_move == thickness_object and height_object_to_move == height_object:
        metrics["right_dimensions"] = True

    return metrics


def check_height_increase(guid, ifc_file, edited_ifc_file, metrics, ifc_identifier):
    ifc_original = ifcopenshell.open(ifc_file)
    object_to_move = ifc_original.by_guid(guid)

    matrix = ifcopenshell.util.placement.get_local_placement(object_to_move.ObjectPlacement)
    placement_original = matrix[:, 3:][0:3]  # in mm

    x_object_to_move, y_object_to_move, z_object_to_move = list(
        map(lambda x: x / 1000, placement_original))  # converted to m

    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, object_to_move)
    geom = shape.geometry
    width_object_to_move = ifcopenshell.util.shape.get_x(geom)
    height_object_to_move = ifcopenshell.util.shape.get_z(geom)
    thickness_object_to_move = ifcopenshell.util.shape.get_y(geom)
    print(x_object_to_move, y_object_to_move, z_object_to_move, width_object_to_move, height_object_to_move, thickness_object_to_move)
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
    x_object_edited, y_object_edited, z_object_edited = list(
        map(lambda x: x / 1000, placement_edited))  # converted to m
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, edited_object)
    geom = shape.geometry
    width_edited_object = ifcopenshell.util.shape.get_x(geom)
    height_edited_object = ifcopenshell.util.shape.get_z(geom)
    thickness_edited_object = ifcopenshell.util.shape.get_y(geom)

    # check if object size was decreased by 0.5 m
    if abs(height_object_to_move - 0.5 - height_edited_object) < 0.1 and abs(width_object_to_move - width_edited_object) < 0.1 and abs(thickness_object_to_move - thickness_edited_object) < 0.1:
        metrics["right_dimensions"] = True
    else:
        # if no height increase, do not check if location is still the same
        return metrics


    # check if location is still the same
    if abs(x_object_edited - x_object_to_move) < 0.1 and abs(y_object_edited - y_object_to_move) < 0.1 and abs(z_object_edited - z_object_to_move) < 0.1:
        metrics["right_location"] = True

    return metrics

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Decrease the height by 0.5 meters of the slab with the id 11kJIqz$n2Jf_DfJV1SCVP."""
    metrics = {
        "right_location": False,
        "right_dimensions": False,
    }

    metrics_z = metrics.copy()
    metrics_height = metrics.copy()

    # either move the slab up
    slab_metrics_z = check_move_z_axis("11kJIqz$n2Jf_DfJV1SCVP", ifc_file, edited_ifc_file, {key: False for key in metrics.keys()}, "IfcSlab")
    metrics_z.update(slab_metrics_z)

    # or increase the size of the slab
    window_metrics_height = check_height_increase("11kJIqz$n2Jf_DfJV1SCVP", ifc_file, edited_ifc_file, {key: False for key in metrics.keys()}, "IfcSlab")

    metrics_height.update(window_metrics_height)

    if sum(metrics_z.values()) > sum(metrics_height.values()):
        return metrics_z
    else:
        return metrics_height

#execute_test("../ifc/basic_tasks.ifc", "../results/edited_ifc_gpt-4.1/29/basic_tasks_0.ifc", {})