import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a door with the size of 2 by 1 meters in the wall with id 2UsXAbj6n0fwEWqdkVuHvf."""
    metrics = {
        "object_exists": False, # door was created
        "right_location": False, # door is in wall
        "right_dimensions": False, # door has size 2x1
        "integrity_constraint": False # door has a topological relationship to wall, ie: does opening exist that is filled?
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # get wall and geometry information
    wall = ifc_edited.by_guid("2UsXAbj6n0fwEWqdkVuHvf")
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, wall)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_wall = min(vertices[:, 0])
    x_max_wall = max(vertices[:, 0])
    y_min_wall = min(vertices[:, 1])
    y_max_wall = max(vertices[:, 1])
    z_min_wall = min(vertices[:, 2])
    z_max_wall = max(vertices[:, 2])

    # check if there is a new door
    original_door_guids = set(door.GlobalId for door in ifc_original.by_type("IfcDoor"))
    edited_door_guids = set(door.GlobalId for door in ifc_edited.by_type("IfcDoor"))

    new_door_ids = list(edited_door_guids - original_door_guids)

    if len(new_door_ids) == 0:
        return metrics

    metrics["object_exists"] = True
    door = ifc_edited.by_guid(new_door_ids[0])


    # get geometry information of the new door
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, door)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_door = min(vertices[:, 0])
    x_max_door = max(vertices[:, 0])
    y_min_door = min(vertices[:, 1])
    y_max_door = max(vertices[:, 1])
    z_min_door = min(vertices[:, 2])
    z_max_door = max(vertices[:, 2])

    width_door = ifcopenshell.util.shape.get_x(geom)
    height_door = ifcopenshell.util.shape.get_z(geom)

    # check for right size dimensions
    if height_door == 2.0 and width_door == 1.0:
        metrics["right_dimensions"] = True

    # check for right location (door in wall)
    if x_min_wall <= x_min_door <= x_max_door <= x_max_wall and y_min_wall <= y_min_door <= y_max_door <= y_max_wall and z_min_wall <= z_min_door <= z_max_door <= z_max_wall:
        metrics["right_location"] = True

    # check for new opening
    original_opening_guids = set(opening.GlobalId for opening in ifc_original.by_type("IfcOpeningElement"))
    edited_opening_guids = set(opening.GlobalId for opening in ifc_edited.by_type("IfcOpeningElement"))

    new_opening_ids = list(edited_opening_guids - original_opening_guids)
    if len(new_opening_ids) == 0:
        return metrics

    opening = ifc_edited.by_guid(new_opening_ids[0])

    # get voids and fills relationships of opening, wall and door and check if they exist and correspond
    opening_fills_relationship = list(filter(lambda x: x.is_a("IfcRelFillsElement"), ifc_edited.get_inverse(opening)))
    if len(opening_fills_relationship) == 0:
        return metrics
    opening_fills_relationship = opening_fills_relationship[0].GlobalId

    opening_voids_relationship = list(filter(lambda x: x.is_a("IfcRelVoidsElement"), ifc_edited.get_inverse(opening)))
    if len(opening_voids_relationship) == 0:
        return metrics
    opening_voids_relationship = opening_voids_relationship[0].GlobalId

    door_fills_relationship = list(filter(lambda x: x.is_a("IfcRelFillsElement"), ifc_edited.get_inverse(door)))
    if len(door_fills_relationship) == 0:
        return metrics
    door_fills_relationship = door_fills_relationship[0].GlobalId

    wall_voids_relationship = list(filter(lambda x: x.is_a("IfcRelVoidsElement"), ifc_edited.get_inverse(wall)))
    if len(wall_voids_relationship) == 0:
        return metrics
    wall_voids_relationship = wall_voids_relationship[0].GlobalId


    if opening_fills_relationship != door_fills_relationship or opening_voids_relationship != wall_voids_relationship:
        return metrics

    # every integrity constraint true
    metrics["integrity_constraint"] = True

    return metrics

#execute_test("../ifc/basic_tasks.ifc", "../ifc/basic_tasks.ifc", {})