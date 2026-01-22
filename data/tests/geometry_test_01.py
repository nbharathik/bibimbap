import math

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
    """Prompt: Create a slab that has a width of 0.2m and is placed on the upper outer edges of the 4 columns in the IFC file.

    Perfect criteria (all must be true):
    - a NEW element exists
    - it is an IfcSlab
    - thickness ("width") ~= 0.2m
    - slab bottom is on the top of the 4 corner columns
    - slab spans the outer faces of those 4 columns (not just centered somewhere)

    Partial credit:
    - if another class is created (IfcCovering/IfcPlate/IfcBuildingElementProxy/IfcRoof), geometry metrics can still pass,
      but `right_location` stays False so `perfect` stays False.
    """
    
    metrics = {
        "object_exists": False, 
        "right_location": False, 
        "right_dimensions": False, 
        "integrity_constraint": False
    }

    ifc_edited = ifcopenshell.open(edited_ifc_file)

    unit_scale = 1.0

    slabs = ifc_edited.by_type("IfcSlab")
    if len(slabs) != 1:
        return metrics

    slab = slabs[0]
    try:
        slab_bbox = _bbox_in_meters(slab, unit_scale)
    except Exception:
        return metrics

    metrics["object_exists"] = True
    metrics["integrity_constraint"] = bool(slab.is_a("IfcSlab"))

    extents = [slab_bbox["x_len"], slab_bbox["y_len"], slab_bbox["z_len"]]
    thickness_est = min(extents)
    if _within_abs(thickness_est, 0.2, tol=0.02):
        metrics["right_dimensions"] = True

    # --- columns: this IFC has exactly 4 columns to begin with
    columns = ifc_edited.by_type("IfcColumn")
    if len(columns) != 4:
        return metrics

    columns_bbox = []
    for col in columns:
        try:
            columns_bbox.append(_bbox_in_meters(col, unit_scale))
        except Exception:
            return metrics

    # compute column top plane and outer edges
    top_z = max(b["z_max"] for b in columns_bbox)
    min_x_edge = min(b["x_min"] for b in columns_bbox)
    max_x_edge = max(b["x_max"] for b in columns_bbox)
    min_y_edge = min(b["y_min"] for b in columns_bbox)
    max_y_edge = max(b["y_max"] for b in columns_bbox)

    slab_z_min = slab_bbox["z_min"]

    # tolerances (meters)
    tol_z = 0.001
    tol_edge = 0.001
    max_overhang = 0.50

    if abs(slab_z_min - top_z) <= tol_z:
        metrics["right_location"] = True

    # "upper outer edges" => slab footprint should reach outer faces of columns.
    spans_outer = (
        slab_bbox["x_min"] <= min_x_edge + tol_edge
        and slab_bbox["x_max"] >= max_x_edge - tol_edge
        and slab_bbox["y_min"] <= min_y_edge + tol_edge
        and slab_bbox["y_max"] >= max_y_edge - tol_edge
    )

    not_too_large = (
        slab_bbox["x_min"] >= min_x_edge - max_overhang
        and slab_bbox["x_max"] <= max_x_edge + max_overhang
        and slab_bbox["y_min"] >= min_y_edge - max_overhang
        and slab_bbox["y_max"] <= max_y_edge + max_overhang
    )

    if spans_outer and not_too_large:
        metrics["right_location"] = True

    final_score = sum(metrics.values()) / len(metrics)

    return metrics
