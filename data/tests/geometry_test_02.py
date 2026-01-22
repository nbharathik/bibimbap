import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


def _bbox_in_meters(product, unit_scale):
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, product)
    geom = shape.geometry
    vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
    vertices = vertices * unit_scale

    x_min = float(vertices[:, 0].min())
    x_max = float(vertices[:, 0].max())
    y_min = float(vertices[:, 1].min())
    y_max = float(vertices[:, 1].max())
    z_min = float(vertices[:, 2].min())
    z_max = float(vertices[:, 2].max())

    return {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "z_min": z_min,
        "z_max": z_max,
        "x_len": x_max - x_min,
        "y_len": y_max - y_min,
        "z_len": z_max - z_min,
        "x_c": (x_min + x_max) / 2.0,
        "y_c": (y_min + y_max) / 2.0,
        "z_c": (z_min + z_max) / 2.0,
    }


def _within_abs(value, expected, tol):
    return abs(value - expected) <= tol


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: create a column in the centroid of the 4 walls in this IFC file."""

    metrics = {
        "object_exists": False,
        "integrity_constraint": False, # 
        "right_location": False, 
        "right_dimensions": False,
    }

    ifc_edited = ifcopenshell.open(edited_ifc_file)
    unit_scale = 1.0

    columns = ifc_edited.by_type("IfcColumn")
    if len(columns) == 0:
        return metrics

    column = columns[-1]
    try:
        col_bbox = _bbox_in_meters(column, unit_scale)
    except Exception:
        return metrics

    metrics["object_exists"] = True
    metrics["right_dimensions"] = metrics["object_exists"]
    metrics["integrity_constraint"] = bool(column.is_a("IfcColumn"))

    walls = ifc_edited.by_type("IfcWall")
    if len(walls) < 4:
        return metrics

    wall_bboxes = []
    for wall in walls:
        try:
            wall_bboxes.append(_bbox_in_meters(wall, unit_scale))
        except Exception:
            continue

    if len(wall_bboxes) < 4:
        return metrics

    avg_x_c = sum(b["x_c"] for b in wall_bboxes) / len(wall_bboxes)
    avg_y_c = sum(b["y_c"] for b in wall_bboxes) / len(wall_bboxes)

    min_x = min(b["x_min"] for b in wall_bboxes)
    max_x = max(b["x_max"] for b in wall_bboxes)
    min_y = min(b["y_min"] for b in wall_bboxes)
    max_y = max(b["y_max"] for b in wall_bboxes)
    box_x_c = (min_x + max_x) / 2.0
    box_y_c = (min_y + max_y) / 2.0

    tol_xy = 0.05
    at_centroid_avg = _within_abs(col_bbox["x_c"], avg_x_c, tol_xy) and _within_abs(col_bbox["y_c"], avg_y_c, tol_xy)
    at_centroid_box = _within_abs(col_bbox["x_c"], box_x_c, tol_xy) and _within_abs(col_bbox["y_c"], box_y_c, tol_xy)

    ground_z = min(b["z_min"] for b in wall_bboxes)
    if (at_centroid_avg or at_centroid_box) or _within_abs(col_bbox["z_min"], ground_z, tol=0.05):
        metrics["right_location"] = True
        
    

    return metrics
