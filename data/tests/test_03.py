import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import math

def execute_test(ifc_file, edited_ifc_file, model_output):
    """returns dict with key for every metric and value true/false"""
    """ifc_file state at beginning: empty"""
    """prompt: Create a wall with 1m height and 2m width and 50cm thickness"""

    return_object = {
        "object_exists": False,
        "right_location": False,
        "right_dimensions": False,
        "right_angle": False
    }

    ifc_edited = ifcopenshell.open(edited_ifc_file)
    try:
        wall = ifc_edited.by_type("IfcWall")[0]
        return_object["object_exists"] = True
    except IndexError:
        return return_object

    matrix = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)
    x, y, z = matrix[:,3][:3]

    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, wall)
    geom = shape.geometry
    width = ifcopenshell.util.shape.get_x(geom)
    height = ifcopenshell.util.shape.get_z(geom)
    thickness = ifcopenshell.util.shape.get_y(geom)

    if width == 2.0 and height == 1.0 and thickness == 0.5:
        return_object["right_dimensions"] = True

    placement = wall.ObjectPlacement
    rel = placement.RelativePlacement
    dir_x = rel.RefDirection.DirectionRatios if rel.RefDirection else [1, 0, 0]
    angle = math.degrees(math.atan2(dir_x[1], dir_x[0]))

    if angle == 90:
        return_object["right_angle"] = True

    if x == 0.0 and y == 0.0 and z == 0.0:
        return_object["right_location"] = True

    return return_object
