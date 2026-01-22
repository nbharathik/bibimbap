import ifcopenshell
import os
import ifcopenshell.geom
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Insert a column to the inner sapace of the walls with ids [GlobalId = "3_DHXxtdb3wRKlXgyMiHOP",
    GlobalId = "3_DHXxtdb3wRKlXgyMiHR$", GlobalId = "3_DHXxtdb3wRKlXgyMiH5o", GlobalId = "1IMYx2Ej12vu3iYKHoTn08"]")."""
    metrics = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "integrity_constraint": False,  # NEW
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new column
    original_column_guids = set(col.GlobalId for col in ifc_original.by_type("IfcColumn"))
    edited_column_guids = set(col.GlobalId for col in ifc_edited.by_type("IfcColumn"))

    new_column_ids = list(edited_column_guids - original_column_guids)
    if len(new_column_ids) == 0:
        metrics["integrity_constraint"] = all(
            metrics[k] for k in ("object_exists", "right_location", "right_dimensions")
        )
        return metrics

    metrics["object_exists"] = True
    column = ifc_edited.by_guid(new_column_ids[0])

    # get column geometry information
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, column)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_col = min(vertices[:, 0])
    x_max_col = max(vertices[:, 0])
    y_min_col = min(vertices[:, 1])
    y_max_col = max(vertices[:, 1])
    z_min_col = min(vertices[:, 2])
    z_max_col = max(vertices[:, 2])

    # column center point
    col_center_x = (x_min_col + x_max_col) / 2
    col_center_y = (y_min_col + y_max_col) / 2

    # get wall geometry information to determine the inner space
    wall_ids = ["3_DHXxtdb3wRKlXgyMiHOP", "3_DHXxtdb3wRKlXgyMiHR$",
                "3_DHXxtdb3wRKlXgyMiH5o", "1IMYx2Ej12vu3iYKHoTn08"]

    try:
        wall_bounds = []
        for wall_id in wall_ids:
            try:
                wall = ifc_edited.by_guid(wall_id)
                wall_shape = ifcopenshell.geom.create_shape(settings, wall)
                wall_geom = wall_shape.geometry
                wall_vertices = ifcopenshell.util.shape.get_shape_vertices(wall_shape, wall_geom)
                wall_bounds.append({
                    'x_min': min(wall_vertices[:, 0]),
                    'x_max': max(wall_vertices[:, 0]),
                    'y_min': min(wall_vertices[:, 1]),
                    'y_max': max(wall_vertices[:, 1])
                })
            except:
                continue

        if len(wall_bounds) >= 4:
            # calculate the bounding box of the inner space
            x_min_space = min(wb['x_min'] for wb in wall_bounds)
            x_max_space = max(wb['x_max'] for wb in wall_bounds)
            y_min_space = min(wb['y_min'] for wb in wall_bounds)
            y_max_space = max(wb['y_max'] for wb in wall_bounds)

            # check if column center is within the inner space
            tolerance = 1.0
            if (x_min_space - tolerance <= col_center_x <= x_max_space + tolerance and
                y_min_space - tolerance <= col_center_y <= y_max_space + tolerance):
                metrics["right_location"] = True

            # check if column has reasonable dimensions (not too small, not too large)
            col_width = x_max_col - x_min_col
            col_depth = y_max_col - y_min_col
            col_height = z_max_col - z_min_col

            # typical column dimensions: 0.2m to 1.0m for width/depth
            if (0.1 <= col_width <= 2.0 and 0.1 <= col_depth <= 2.0 and col_height > 1.0):
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
    result = execute_test("data/02/01_02_002.ifc", "tests/02/02/results/02/01_02_002.ifc", {})
    print("\nTest Results:")
    print(f"  object_exists: {result['object_exists']}")
    print(f"  right_location: {result['right_location']}")
    print(f"  right_dimensions: {result['right_dimensions']}")
    print(f"  integrity_constraint: {result['integrity_constraint']}")  # NEW