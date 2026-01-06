import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Insert a column with the height of 3m in (12, 8)."""
    metrics = {
        "object_exists": False, # column was created
        "right_location": False, # column is in (12, 8)
        "right_dimensions": False # column has height of 3m
    }

    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    # check if there is a new column
    original_column_guids = set(column.GlobalId for column in ifc_original.by_type("IfcColumn"))
    edited_column_guids = set(column.GlobalId for column in ifc_edited.by_type("IfcColumn"))

    new_column_ids = list(edited_column_guids - original_column_guids)
    if len(new_column_ids) == 0:
        return metrics
    metrics["object_exists"] = True
    column = ifc_edited.by_guid(new_column_ids[0])

    # get column geometry information
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, column)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    x_min_column = min(vertices[:, 0])
    x_max_column = max(vertices[:, 0])
    y_min_column = min(vertices[:, 1])
    y_max_column = max(vertices[:, 1])
    z_min_column = min(vertices[:, 2])
    z_max_column = max(vertices[:, 2])

    width_column = ifcopenshell.util.shape.get_x(geom)
    height_column = ifcopenshell.util.shape.get_z(geom)
    thickness_column = ifcopenshell.util.shape.get_y(geom)

    if height_column == 3.0:
        metrics["right_dimensions"] = True

    if (x_min_column <= 12.0 <= x_max_column and y_min_column <= 8.0 <= y_max_column) or (x_min_column <= 8.0 <= x_max_column and y_min_column <= 12.0 <= y_max_column):
        metrics["right_location"] = True

    return metrics

#execute_test("../ifc/basic_tasks.ifc", "../results/edited_ifc_gpt-4.1/15/basic_tasks_0.ifc", {})