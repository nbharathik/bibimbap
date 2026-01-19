import math
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


COLUMN_GUIDS = [
    "3lOEkLxYb9$uRd50gnIDtk",
    "3lOEkLxYb9$uRd50gnIDtl",
    "3lOEkLxYb9$uRd50gnIDpA",
    "3lOEkLxYb9$uRd50gnIDqu",
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


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def _forms_rectangle(centers, tolerance=0.3):
    if len(centers) != 4:
        return False
    
    x_coords = [c[0] for c in centers]
    y_coords = [c[1] for c in centers]
    
    x_coords_sorted = sorted(x_coords)
    y_coords_sorted = sorted(y_coords)
    
    x_unique = []
    for x in x_coords_sorted:
        if not x_unique or abs(x - x_unique[-1]) > tolerance:
            x_unique.append(x)
    
    y_unique = []
    for y in y_coords_sorted:
        if not y_unique or abs(y - y_unique[-1]) > tolerance:
            y_unique.append(y)
    
    if len(x_unique) != 2 or len(y_unique) != 2:
        return False
    
    expected_centers = []
    for x in x_unique:
        for y in y_unique:
            expected_centers.append((x, y))
    
    for center in centers:
        matched = False
        for expected in expected_centers:
            if abs(center[0] - expected[0]) <= tolerance and abs(center[1] - expected[1]) <= tolerance:
                matched = True
                break
        if not matched:
            return False
    
    return True


def execute_test(ifc_file, edited_ifc_file, model_output):
    metrics = {
        "forms_rectangle": False,
    }

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    unit_scale = 1.0

    columns = []
    for guid in COLUMN_GUIDS:
        col = _safe_by_guid(ifc_edited, guid)
        if col is None:
            return metrics
        columns.append(col)

    try:
        centers = []
        for col in columns:
            bbox = _bbox_in_meters(col, unit_scale)
            centers.append((bbox["x_c"], bbox["y_c"]))
        
        metrics["forms_rectangle"] = _forms_rectangle(centers)
        
    except Exception:
        return metrics

    return metrics
