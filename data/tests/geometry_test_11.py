import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


WALL_GUIDS = [
    "3PQZwOmmD1hgPWgX4XFLJO",
    "3PQZwOmmD1hgPWgX4XFLJP",
    "3PQZwOmmD1hgPWgX4XFLJQ",
    "3PQZwOmmD1hgPWgX4XFLJR",
    "3PQZwOmmD1hgPWgX4XFLJV",
    "3PQZwOmmD1hgPWgX4XFLJU",
]


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


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: decrease the height of all walls by 0.5 m on the 2nd storey.

    Expected behavior:
    - All walls with the specified GUIDs should have their height reduced by 0.5m.
    - All specified walls should still exist in the edited IFC.

    Metrics:
    - all_walls_exist: All 6 walls are still present
    - all_heights_reduced_correctly: All walls have height reduced by 0.5m (±0.05m tolerance)
    - Individual wall checks: wall_{i}_height_correct for each wall
    """

    metrics = {
        "integrity_constraint": False,
        "right_dimensions": False,
        "right_location": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    unit_scale = 1.0
    height_reduction = 0.5
    height_tolerance = 0.05

    walls_original = []
    walls_edited = []
    
    for guid in WALL_GUIDS:
        wall_orig = _safe_by_guid(ifc_original, guid)
        wall_edit = _safe_by_guid(ifc_edited, guid)
        
        if wall_orig is None or wall_edit is None:
            return metrics
        
        walls_original.append(wall_orig)
        walls_edited.append(wall_edit)

    # Compare heights and check if reduced by 0.5m
    heights_correct = []
    for idx, (wall_orig, wall_edit) in enumerate(zip(walls_original, walls_edited)):
        try:
            bbox_orig = _bbox_in_meters(wall_orig, unit_scale)
            bbox_edit = _bbox_in_meters(wall_edit, unit_scale)
            
            original_height = bbox_orig["z_len"]
            edited_height = bbox_edit["z_len"]
            height_diff = original_height - edited_height
            
            is_correct = _within_abs(height_diff, height_reduction, height_tolerance)
            # metrics[f"wall_{idx+1}_height_correct"] = is_correct
            heights_correct.append(is_correct)
        except Exception:
            heights_correct.append(False)
            continue
    
    metrics["integrity_constraint"] = all(
        wall_orig.is_a("IfcWall") and wall_edit.is_a("IfcWall")
        for wall_orig, wall_edit in zip(walls_original, walls_edited)
    )
    metrics["right_dimensions"] = all(heights_correct)
    metrics["right_location"] = metrics["right_dimensions"]

    return metrics
