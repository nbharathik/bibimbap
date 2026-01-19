import math
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


TARGET_WALL_GUID = "1$zxNs50z3OeFBpABtoN6K" # Wall to be rotated


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


def _get_wall_direction_angle(wall, unit_scale):
    """Calculate the orientation angle of a wall in the XY plane.
    
    Returns angle in degrees from the positive X-axis, measured counter-clockwise.
    For a wall primarily aligned with an axis, we determine the longer direction.
    """
    try:
        bbox = _bbox_in_meters(wall, unit_scale)
        
        x_len = bbox["x_len"]
        y_len = bbox["y_len"]
        
        if x_len > y_len:
            angle = 0.0
        else:
            angle = 90.0
            
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, wall)
        geom = shape.geometry
        vertices = ifcopenshell.util.shape.get_shape_vertices(shape, geom)
        vertices = vertices * unit_scale
        
        xy_vertices = vertices[:, :2]
        
        max_dist = 0
        p1, p2 = None, None
        for i in range(len(xy_vertices)):
            for j in range(i + 1, len(xy_vertices)):
                dist = np.linalg.norm(xy_vertices[i] - xy_vertices[j])
                if dist > max_dist:
                    max_dist = dist
                    p1 = xy_vertices[i]
                    p2 = xy_vertices[j]
        
        direction = p2 - p1
        
        angle = math.degrees(math.atan2(direction[1], direction[0]))
        
        angle = angle % 180
        
        return angle
        
    except Exception as e:
        bbox = _bbox_in_meters(wall, unit_scale)
        x_len = bbox["x_len"]
        y_len = bbox["y_len"]
        
        if x_len > y_len:
            return 0.0
        else:
            return 90.0


def _angle_difference(angle1, angle2):
    """Calculate the smallest angle difference between two angles.
    
    Handles wraparound (e.g., 179° and 1° are 2° apart, not 178°)
    Returns difference in range [0, 180]
    """
    diff = abs(angle1 - angle2) % 180
    if diff > 90:
        diff = 180 - diff
    return diff


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: rotate wall by +45° around its center which is parallel to wall with GlobalId = "1$zxNs50z3OeFBpABtoN40"

    Expected behavior:
    - The wall with GUID "1$zxNs50z3OeFBpABtoN6K" should be rotated by 45 degrees.

    Metrics:
    - rotation_correct: The wall has been rotated by 45° (±1° tolerance)
    """

    metrics = {
        "rotation_correct": False,
    }

    try:
        ifc_original = ifcopenshell.open(ifc_file)
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    unit_scale = 1.0
    rotation_angle = 45.0
    angle_tolerance = 1.0

    wall_original = _safe_by_guid(ifc_original, TARGET_WALL_GUID)
    wall_edited = _safe_by_guid(ifc_edited, TARGET_WALL_GUID)

    if wall_original is None or wall_edited is None:
        return metrics

    try:
        # Get wall directions
        angle_original = _get_wall_direction_angle(wall_original, unit_scale)
        angle_edited = _get_wall_direction_angle(wall_edited, unit_scale)
        
        print(f"Original angle: {angle_original}, Edited angle: {angle_edited}")
        
        rotation_diff = _angle_difference(angle_edited, angle_original)
        
        metrics["rotation_correct"] = abs(rotation_diff - rotation_angle) <= angle_tolerance
        
    except Exception:
        return metrics

    return metrics
