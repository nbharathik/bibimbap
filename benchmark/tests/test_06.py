import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape


def execute_test(ifc_file, edited_ifc_file, model_output):
    """returns dict with key for every metric and value true/false"""

    return_object = {
        "objects_exist": False,
        "right_location": False,
        "right_dimensions": False
    }

    ifc_edited = ifcopenshell.open(edited_ifc_file)

    wall = ifc_edited.by_id(508)

    openings = ifc_edited.by_type("IfcOpeningElement")
    for opening in openings:
        print(opening)



    return return_object
