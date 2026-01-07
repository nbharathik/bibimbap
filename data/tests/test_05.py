import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add a wall with a length of 15m beginning in (0, -10)."""
    metrics = {
        "object_exists": False, # wall was created
        "right_location": False, # wall starts at (0, -10)
        "right_dimensions": False # wall has length of 15m
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new wall
    original_wall_guids = set(wall.GlobalId for wall in ifc_original.by_type("IfcWall"))
    edited_wall_guids = set(wall.GlobalId for wall in ifc_edited.by_type("IfcWall"))

    new_wall_ids = list(edited_wall_guids - original_wall_guids)
    if len(new_wall_ids) == 0:
        return metrics
    metrics["object_exists"] = True
    wall = ifc_edited.by_guid(new_wall_ids[0])

    # get column geometry information
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

    width_wall = ifcopenshell.util.shape.get_x(geom)
    height_wall = ifcopenshell.util.shape.get_z(geom)
    thickness_wall = ifcopenshell.util.shape.get_y(geom)

    if width_wall == 15.0 or thickness_wall == 15.0:
        metrics["right_dimensions"] = True

    if (x_min_wall == 0.0 and (y_min_wall == -10.0 or y_max_wall == -10.0)) or (x_max_wall == 0.0 and (y_min_wall == -10.0 or y_max_wall == -10.0)):
        metrics["right_location"] = True

    return metrics

#execute_test("../ifc/basic_tasks.ifc", "../results/edited_ifc_gpt-4.1/15/basic_tasks_0.ifc", {})