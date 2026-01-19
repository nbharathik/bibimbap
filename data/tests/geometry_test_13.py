import math
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


WINDOW_GUIDS = [
    "2KbOAL4v52mv2YJ6fTql5D",
    "2KbOAL4v52mv2YJ6fTql5C",
    "2KbOAL4v52mv2YJ6fTql5F",
    "2KbOAL4v52mv2YJ6fTql5A",
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
    """Prompt: move the window by 3m along the x axis which is wider than 1.50m

    Expected behavior:
    - All window objects (4 GUIDs) should be moved by 3m in positive X direction.
    - All window objects should still exist in the edited IFC.

    Metrics:
    - movement_correct: All window objects moved by 3m (±0.1m tolerance) along X-axis
    """

    metrics = {
        "movement_correct": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    unit_scale = 1.0
    expected_movement = 3.0
    movement_tolerance = 0.1

    window_objects_original = []
    window_objects_edited = []
    
    for guid in WINDOW_GUIDS:
        obj_orig = _safe_by_guid(ifc_original, guid)
        obj_edit = _safe_by_guid(ifc_edited, guid)
        
        if obj_orig is None or obj_edit is None:
            return metrics
        
        window_objects_original.append(obj_orig)
        window_objects_edited.append(obj_edit)

    all_moved_correctly = True
    
    for obj_orig, obj_edit in zip(window_objects_original, window_objects_edited):
        try:
            bbox_orig = _bbox_in_meters(obj_orig, unit_scale)
            bbox_edit = _bbox_in_meters(obj_edit, unit_scale)
            
            x_movement = bbox_edit["x_c"] - bbox_orig["x_c"]
            
            if not _within_abs(x_movement, expected_movement, movement_tolerance):
                all_moved_correctly = False
                break
            
            y_movement = abs(bbox_edit["y_c"] - bbox_orig["y_c"])
            z_movement = abs(bbox_edit["z_c"] - bbox_orig["z_c"])
            
            if y_movement > 0.1 or z_movement > 0.1:
                all_moved_correctly = False
                break
                
        except Exception:
            all_moved_correctly = False
            break

    metrics["movement_correct"] = all_moved_correctly
    return metrics
