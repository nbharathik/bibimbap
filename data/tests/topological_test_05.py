import ifcopenshell
import os
import ifcopenshell.geom
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Create a door in one of the existing walls so that it connects the inner space with the outdoor space."""
    metrics = {
        "object_exists": False, 
        "right_location": False,
        "right_dimensions": False 
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new door
    original_door_guids = set(door.GlobalId for door in ifc_original.by_type("IfcDoor"))
    edited_door_guids = set(door.GlobalId for door in ifc_edited.by_type("IfcDoor"))

    new_door_ids = list(edited_door_guids - original_door_guids)
    if len(new_door_ids) == 0:
        return metrics
    metrics["object_exists"] = True
    door = ifc_edited.by_guid(new_door_ids[0])

    # get door geometry information
    settings = ifcopenshell.geom.settings()
    try:
        shape = ifcopenshell.geom.create_shape(settings, door)
        geom = shape.geometry
        vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
        x_min_door = min(vertices[:, 0])
        x_max_door = max(vertices[:, 0])
        y_min_door = min(vertices[:, 1])
        y_max_door = max(vertices[:, 1])
        z_min_door = min(vertices[:, 2])
        z_max_door = max(vertices[:, 2])

        door_width = x_max_door - x_min_door
        door_depth = y_max_door - y_min_door
        door_height = z_max_door - z_min_door

        # check if door has typical dimensions (right_dimensions)
        # typical door: width 0.7-1.2m, height 1.8-2.5m, depth 0.05-0.3m
        if (0.6 <= door_width <= 1.5 and 1.5 <= door_height <= 3.0) or \
           (0.6 <= door_depth <= 1.5 and 1.5 <= door_height <= 3.0):
            metrics["right_dimensions"] = True

        # door center point
        door_center_x = (x_min_door + x_max_door) / 2
        door_center_y = (y_min_door + y_max_door) / 2
        door_center_z = (z_min_door + z_max_door) / 2
    except:
        # if door geometry cannot be created, still check relationships
        door_center_x = door_center_y = door_center_z = None

    # check if door is located in/on a wall (right_location)
    try:
        # Method 1: Check IFC relationships (IfcRelVoidsElement)
        door_in_wall = False
        for rel in ifc_edited.by_type("IfcRelVoidsElement"):
            if rel.RelatedOpeningElement:
                # Check if this opening has the door
                for rel_fills in ifc_edited.by_type("IfcRelFillsElement"):
                    if rel_fills.RelatingOpeningElement == rel.RelatedOpeningElement:
                        if rel_fills.RelatedBuildingElement == door:
                            # This door fills an opening in a wall
                            if rel.RelatingBuildingElement.is_a("IfcWall"):
                                door_in_wall = True
                                break
        
        # Method 2: Check geometric proximity to walls
        if not door_in_wall and door_center_x is not None:
            walls = ifc_edited.by_type("IfcWall")
            for wall in walls:
                try:
                    wall_shape = ifcopenshell.geom.create_shape(settings, wall)
                    wall_geom = wall_shape.geometry
                    wall_vertices = ifcopenshell.util.shape.get_shape_vertices(wall_shape, wall_geom)
                    x_min_wall = min(wall_vertices[:, 0])
                    x_max_wall = max(wall_vertices[:, 0])
                    y_min_wall = min(wall_vertices[:, 1])
                    y_max_wall = max(wall_vertices[:, 1])
                    z_min_wall = min(wall_vertices[:, 2])
                    z_max_wall = max(wall_vertices[:, 2])

                    # check if door center is within wall bounds (with tolerance)
                    tolerance = 0.5
                    if (x_min_wall - tolerance <= door_center_x <= x_max_wall + tolerance and
                        y_min_wall - tolerance <= door_center_y <= y_max_wall + tolerance and
                        z_min_wall - tolerance <= door_center_z <= z_max_wall + tolerance):
                        door_in_wall = True
                        break
                except:
                    continue
        
        if door_in_wall:
            metrics["right_location"] = True

    except Exception:
        pass

    return metrics