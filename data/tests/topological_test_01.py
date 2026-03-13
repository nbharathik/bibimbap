import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Add a wall to the room with the id "GlobalId = "3_DHXxtdb3wRKlXgyMiH4s"
        so that it gets fully enclosed")."""
    metrics = {
        "object_exists": False, 
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,  # NEW
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new wall
    original_wall_guids = set(wall.GlobalId for wall in ifc_original.by_type("IfcWall"))
    edited_wall_guids = set(wall.GlobalId for wall in ifc_edited.by_type("IfcWall"))

    new_wall_ids = list(edited_wall_guids - original_wall_guids)
    if len(new_wall_ids) == 0:
        metrics["integrity_constraint"] = all(
            metrics[k] for k in ("object_exists", "right_location", "right_dimensions")
        )
        return metrics

    metrics["object_exists"] = True
    wall = ifc_edited.by_guid(new_wall_ids[0])

    # get wall geometry information
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

    # get room geometry information
    try:
        room = ifc_edited.by_guid("3_DHXxtdb3wRKlXgyMiH4s")
        room_shape = ifcopenshell.geom.create_shape(settings, room)
        room_geom = room_shape.geometry
        room_vertices = ifcopenshell.util.shape.get_shape_vertices(room_shape, room_geom)
        x_min_room = min(room_vertices[:, 0])
        x_max_room = max(room_vertices[:, 0])
        y_min_room = min(room_vertices[:, 1])
        y_max_room = max(room_vertices[:, 1])
        
        width_room = ifcopenshell.util.shape.get_x(room_geom)
        depth_room = ifcopenshell.util.shape.get_y(room_geom)
        
        # check if wall is at one of the room boundaries (right_location)
        tolerance = 0.5
        at_boundary = (
            abs(x_min_wall - x_min_room) < tolerance or 
            abs(x_max_wall - x_max_room) < tolerance or
            abs(y_min_wall - y_min_room) < tolerance or 
            abs(y_max_wall - y_max_room) < tolerance
        )
        print(x_min_wall)
        print(x_min_room)
        
        if at_boundary:
            metrics["right_location"] = True
        
        # check if wall dimensions match room opening (right_dimensions)
        wall_length = max(width_wall, thickness_wall)
        room_dimension = max(width_room, depth_room)
        if abs(wall_length - room_dimension) < tolerance or abs(wall_length - min(width_room, depth_room)) < tolerance:
            metrics["right_dimensions"] = True
            
    except Exception:
        pass

    # NEW: integrity constraint = all other metrics are true
    metrics["integrity_constraint"] = all(
        metrics[k] for k in ("object_exists", "right_location", "right_dimensions")
    )
    return metrics

