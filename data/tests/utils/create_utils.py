"""
Shared utility functions for CREATE test scripts.

Provides reusable patterns for:
- Geometry extraction (bounding box)
- New element detection
- Dimension matching with tolerance
- Integrity sub-check computation
- Fills/Voids relationship verification
"""

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.shape


# Geometry helpers -----------------------------------------------------

def get_bbox(product, unit_scale=1.0):
    """
    Compute the world-space axis-aligned bounding box of an IFC product.

    Returns a dict with keys: x_min, x_max, y_min, y_max, z_min, z_max,
    x_len, y_len, z_len, x_c, y_c, z_c (center coordinates).

    Raises RuntimeError if geometry cannot be created.
    """
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
        "x_min": x_min, "x_max": x_max,
        "y_min": y_min, "y_max": y_max,
        "z_min": z_min, "z_max": z_max,
        "x_len": x_max - x_min,
        "y_len": y_max - y_min,
        "z_len": z_max - z_min,
        "x_c": (x_min + x_max) / 2.0,
        "y_c": (y_min + y_max) / 2.0,
        "z_c": (z_min + z_max) / 2.0,
    }


def get_shape_dims(product):
    """
    Get the oriented shape dimensions (x, y, z) using ifcopenshell.util.shape.

    Returns (width, depth, height) as floats, or None on failure.
    """
    try:
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, product)
        geom = shape.geometry
        width = ifcopenshell.util.shape.get_x(geom)
        depth = ifcopenshell.util.shape.get_y(geom)
        height = ifcopenshell.util.shape.get_z(geom)
        return (width, depth, height)
    except RuntimeError:
        return None


def within_abs(value, expected, tol):
    """Check if value is within absolute tolerance of expected."""
    return abs(float(value) - float(expected)) <= tol


def dims_match(actual_pair, expected_pair, tol=0.05):
    """
    Check if two dimension values match in any order.

    E.g., dims_match((2.0, 1.0), (1.0, 2.0), tol=0.05) → True
    actual_pair and expected_pair are each 2-tuples of float values.
    """
    a1, a2 = float(actual_pair[0]), float(actual_pair[1])
    e1, e2 = float(expected_pair[0]), float(expected_pair[1])

    # Try both orderings
    match_direct = within_abs(a1, e1, tol) and within_abs(a2, e2, tol)
    match_swapped = within_abs(a1, e2, tol) and within_abs(a2, e1, tol)
    return match_direct or match_swapped


def point_in_bbox_xy(px, py, bbox, tol=0.5):
    """
    Check if a 2D point (px, py) falls within or near the XY footprint
    of a bounding box, with tolerance.
    """
    return (bbox["x_min"] - tol <= px <= bbox["x_max"] + tol and
            bbox["y_min"] - tol <= py <= bbox["y_max"] + tol)


def bbox_contains_bbox(outer, inner, tol=0.1):
    """Check if inner bounding box is contained within outer, with tolerance."""
    return (outer["x_min"] - tol <= inner["x_min"] and
            inner["x_max"] <= outer["x_max"] + tol and
            outer["y_min"] - tol <= inner["y_min"] and
            inner["y_max"] <= outer["y_max"] + tol and
            outer["z_min"] - tol <= inner["z_min"] and
            inner["z_max"] <= outer["z_max"] + tol)



# New element detection -----------------------------------------------

def find_new_elements(original, edited, ifc_type):
    """
    Find elements of a given IFC type that exist in the edited model
    but not in the original.

    Args:
        original: opened ifcopenshell model (original IFC file)
        edited: opened ifcopenshell model (edited IFC file)
        ifc_type: IFC type string, e.g. "IfcDoor", "IfcWall"

    Returns:
        List of new IFC element instances.
    """
    original_guids = set(
        e.GlobalId for e in original.by_type(ifc_type)
        if getattr(e, "GlobalId", None)
    )
    edited_elements = edited.by_type(ifc_type)

    new_elements = [
        e for e in edited_elements
        if getattr(e, "GlobalId", None) and e.GlobalId not in original_guids
    ]
    return new_elements



# Integrity sub-checks (each returns 1.0 for pass, 0.0 for fail) ------------------------------

def check_is_correct_type(element, expected_type):
    """Check if element is of the expected IFC type. Returns 1.0 or 0.0."""
    return 1.0 if element.is_a(expected_type) else 0.0


def check_spatial_containment(model, element):
    """
    Check if element is contained in a spatial structure via
    IfcRelContainedInSpatialStructure. Returns 1.0 or 0.0.
    """
    try:
        for rel in model.by_type("IfcRelContainedInSpatialStructure"):
            related = rel.RelatedElements
            if related and element in related:
                return 1.0
    except Exception:
        pass
    return 0.0


def check_valid_representation(element):
    """Check if element has a non-empty geometry representation. Returns 1.0 or 0.0."""
    rep = getattr(element, "Representation", None)
    if rep is None:
        return 0.0
    representations = getattr(rep, "Representations", None)
    if not representations:
        return 0.0
    for shape_rep in representations:
        items = getattr(shape_rep, "Items", None)
        if items and len(items) > 0:
            return 1.0
    return 0.0


def check_elements_preserved(original, edited):
    """
    Check that all original GUIDs are still present in edited model.
    Returns 1.0 or 0.0.
    """
    original_guids = {
        e.GlobalId for e in original.by_type("IfcRoot")
        if getattr(e, "GlobalId", None)
    }
    edited_guids = {
        e.GlobalId for e in edited.by_type("IfcRoot")
        if getattr(e, "GlobalId", None)
    }
    return 1.0 if original_guids.issubset(edited_guids) else 0.0


def check_fills_voids_chain(model, fill_element, void_parent):
    """
    Check the IFC relationship chain: fill_element → IfcRelFillsElement → IfcOpeningElement
    → IfcRelVoidsElement → void_parent.

    Used for doors/windows that must fill an opening that voids a wall/slab.

    Args:
        model: opened ifcopenshell model
        fill_element: the door or window element
        void_parent: the wall or slab element that should be voided

    Returns:
        1.0 if full chain exists, 0.0 otherwise.
    """
    try:
        # Find opening that this element fills
        for rel_fills in model.by_type("IfcRelFillsElement"):
            if rel_fills.RelatedBuildingElement != fill_element:
                continue

            opening = rel_fills.RelatingOpeningElement
            if not opening or not opening.is_a("IfcOpeningElement"):
                continue

            # Check that this opening voids the parent element
            for rel_voids in model.by_type("IfcRelVoidsElement"):
                if (rel_voids.RelatedOpeningElement == opening and
                        rel_voids.RelatingBuildingElement == void_parent):
                    return 1.0
    except Exception:
        pass
    return 0.0


def check_voids_relationship(model, opening_element, parent_element):
    """
    Check that an opening element voids a parent element via IfcRelVoidsElement.

    Args:
        model: opened ifcopenshell model
        opening_element: the IfcOpeningElement
        parent_element: the parent element (e.g., IfcSlab) that should be voided

    Returns:
        1.0 if the relationship exists, 0.0 otherwise.
    """
    try:
        for rel in model.by_type("IfcRelVoidsElement"):
            if (rel.RelatedOpeningElement == opening_element and
                    rel.RelatingBuildingElement == parent_element):
                return 1.0
    except Exception:
        pass
    return 0.0



# Integrity aggregation ----------------------------------------------

def compute_integrity(sub_checks, extra_objects_penalty=False):
    """
    Compute integrity constraint score as average of sub-checks.

    Args:
        sub_checks: list of float values (each 0.0 or 1.0)
        extra_objects_penalty: if True, multiply result by 0.5
            (used when LLM created more objects than asked for)

    Returns:
        float between 0.0 and 1.0
    """
    if not sub_checks:
        return 0.0

    avg = sum(sub_checks) / len(sub_checks)

    if extra_objects_penalty:
        avg *= 0.5

    return round(avg, 4)
