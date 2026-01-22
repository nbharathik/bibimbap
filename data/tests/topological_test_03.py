import ifcopenshell
import os
import ifcopenshell.geom
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Insert a wall that separates the rooms with the ids[ GlobalId = "0rMMWWDi1E0Qbe7dlPjRaK", 
    GlobalId = "0rMMWWDi1E0Qbe7dlPjRcx"]]")."""
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

    # wall center point
    wall_center_x = (x_min_wall + x_max_wall) / 2
    wall_center_y = (y_min_wall + y_max_wall) / 2

    # get both room geometry information
    room_ids = ["0rMMWWDi1E0Qbe7dlPjRaK", "0rMMWWDi1E0Qbe7dlPjRcx"]

    try:
        room_bounds = []
        room_centers = []
        for room_id in room_ids:
            try:
                room = ifc_edited.by_guid(room_id)
                room_shape = ifcopenshell.geom.create_shape(settings, room)
                room_geom = room_shape.geometry
                room_vertices = ifcopenshell.util.shape.get_shape_vertices(room_shape, room_geom)
                x_min = min(room_vertices[:, 0])
                x_max = max(room_vertices[:, 0])
                y_min = min(room_vertices[:, 1])
                y_max = max(room_vertices[:, 1])

                room_bounds.append({
                    'x_min': x_min,
                    'x_max': x_max,
                    'y_min': y_min,
                    'y_max': y_max
                })
                room_centers.append({
                    'x': (x_min + x_max) / 2,
                    'y': (y_min + y_max) / 2
                })
            except:
                continue

        if len(room_bounds) >= 2:
            # check if wall is positioned between the two rooms (right_location)
            room1_center = room_centers[0]
            room2_center = room_centers[1]

            # calculate if wall is positioned between room centers
            tolerance = 2.0

            dist_room1_to_wall = ((wall_center_x - room1_center['x'])**2 + (wall_center_y - room1_center['y'])**2)**0.5
            dist_room2_to_wall = ((wall_center_x - room2_center['x'])**2 + (wall_center_y - room2_center['y'])**2)**0.5
            dist_room1_to_room2 = ((room1_center['x'] - room2_center['x'])**2 + (room1_center['y'] - room2_center['y'])**2)**0.5

            # wall should be somewhere between the rooms (not beyond either room)
            if abs((dist_room1_to_wall + dist_room2_to_wall) - dist_room1_to_room2) < tolerance:
                metrics["right_location"] = True

            # check if wall has reasonable dimensions for separating rooms (right_dimensions)
            wall_length = max(width_wall, thickness_wall)

            # wall should have reasonable height (> 1.5m typically) and length
            if height_wall > 1.5 and wall_length > 0.5:
                metrics["right_dimensions"] = True

    except Exception:
        pass

    # NEW: integrity constraint = all other metrics are true
    metrics["integrity_constraint"] = all(
        metrics[k] for k in ("object_exists", "right_location", "right_dimensions")
    )
    return metrics

if __name__ == "__main__":
    path = os.getcwd()
    print(path)
    result = execute_test("data/02/01_02_003.ifc", "tests/02/03/results/02/01_02_003.ifc", {})
    print("\nTest Results:")
    print(f"  object_exists: {result['object_exists']}")
    print(f"  right_location: {result['right_location']}")
    print(f"  right_dimensions: {result['right_dimensions']}")
    print(f"  integrity_constraint: {result['integrity_constraint']}")  # NEW