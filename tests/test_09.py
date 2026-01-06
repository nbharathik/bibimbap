import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape


def execute_test(ifc_file, edited_ifc_file, model_output):
    """returns dict with key for every metric and value true/false"""
    """move door by one meter in x direction"""

    return_object = {
        "right_location": False,
        "integrity_constraint_violated": False,
        "old_object_not_exists": False,
        "new_object_exists": False
    }

    ifc = ifcopenshell.open(ifc_file)
    original_door = ifc.by_guid("11kJIqz$n2Jf_DfJV1SDY7")
    orig_matrix = ifcopenshell.util.placement.get_local_placement(original_door.ObjectPlacement)
    x_orig, y_orig, z_orig = orig_matrix[:, 3][:3]

    ifc_edited = ifcopenshell.open(edited_ifc_file) # TODO: need to identify the new door; take all other doors JUST USE FILE WITH ONLY ONE DOOR
    edited_door = ifc_edited.by_guid("11kJIqz$n2Jf_DfJV1SDY7") # TODO: what if llm deletes old object and created new? Test if there are as many doors in the new file as in the old
    edited_matrix = ifcopenshell.util.placement.get_local_placement(edited_door.ObjectPlacement)
    x_edited, y_edited, z_edited = edited_matrix[:, 3][:3]

    if x_edited == x_orig + 1.0:
        return_object["right_location"] = True

    try:
        fills_relationship = list(filter(lambda x: x.is_a("IfcRelFillsElement"), ifc.get_inverse(original_door)))[0]
        original_opening = list(filter(lambda x: x.is_a("IfcOpeningElement"), ifc.traverse(fills_relationship)))[0]
    except IndexError:
        print("No opening found")

    try:
        fills_relationship = list(filter(lambda x: x.is_a("IfcRelFillsElement"), ifc.get_inverse(edited_door)))[0]
        edited_opening = list(filter(lambda x: x.is_a("IfcOpeningElement"), ifc.traverse(fills_relationship)))[0]
    except IndexError:
        print("No opening found for edited door")


    # if no opening found for edited_door: integrity constraint violated
    # check if opening also x = x+1; if not, integrity constraint violated

    return return_object
