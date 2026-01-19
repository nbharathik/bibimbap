import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.shape
import numpy as np


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Rotate the wall with id 22hyxvAPr65PFt9WZfHSP3 by +90° around the z axis."""
    metrics = {
        "right_location": False, # wall is rotated correctly
        "right_dimensions": False # wall has same l, w, t as before
        # TODO: integrity?, only possible for wall that has topological relationships before
    }

    ifc_original = ifcopenshell.open(ifc_file)
    wall_to_rotate = ifc_original.by_guid("22hyxvAPr65PFt9WZfHSP3")

    matrix = ifcopenshell.util.placement.get_local_placement(wall_to_rotate.ObjectPlacement)
    placement_original = matrix[:, 0:3][0:3]

    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, wall_to_rotate)
    geom = shape.geometry
    width_wall_to_rotate = ifcopenshell.util.shape.get_x(geom)
    height_wall_to_rotate = ifcopenshell.util.shape.get_z(geom)
    thickness_wall_to_rotate = ifcopenshell.util.shape.get_y(geom)


    """
    strategy:
    1. check if same guid still exists in edited file
        that means object could be updated
        a. check if the update was successful
        
    2. check if new wall exists in edited file
        that means that maybe the update was done by removing and than adding
        a. check if the original wall was removed
            if not: original wall was not removed
        b. check if new wall is the rotated original wall
    
    
    when rotation is successful -> set the old_object_does_not_exist flag to true
    """
    ifc_edited = ifcopenshell.open(edited_ifc_file)
    try:
        edited_wall = ifc_edited.by_guid("22hyxvAPr65PFt9WZfHSP3")
    except RuntimeError:
        # wall to rotate does not exist in edited file
        # check if there is a new wall and use this instead
        original_wall_guids = set(wall.GlobalId for wall in ifc_original.by_type("IfcWall"))
        edited_wall_guids = set(wall.GlobalId for wall in ifc_edited.by_type("IfcWall"))
        new_wall_ids = list(edited_wall_guids - original_wall_guids)
        if len(new_wall_ids) == 0:
            # original wall not existent and no new one? -> task failed
            return metrics
        # new wall will be used for tests
        edited_wall = ifc_edited.by_guid(new_wall_ids[0])

    """
    how to test rotation:
    1. there is information about the rotation in the matrix
    2. but does it necessarily have to be? could also be a wall that has swapped width and thickness
    -> so check for those two?
    center of wall is still at the same spot (is it center???) 
        maybe do not care about that? (for now as time is tight)
    -> if all of above is true, location is right
    
    than check for dimensions:
    just check if height is the same, width is either width or thickness and same for thickness
    
    """

    matrix = ifcopenshell.util.placement.get_local_placement(edited_wall.ObjectPlacement)

    # T_new = T_wall · Rz(α)
    a = 90
    r_z = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
    placement_new = matrix[:, 0:3][0:3]

    if placement_new.tolist() == np.matmul(placement_original, r_z).tolist():
        metrics["right_location"] = True

    # width, thickness == thickness, width also would be a valid rotation of a wall by 90 degree?
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, edited_wall)
    geom = shape.geometry
    width_wall = ifcopenshell.util.shape.get_x(geom)
    height_wall = ifcopenshell.util.shape.get_z(geom)
    thickness_wall = ifcopenshell.util.shape.get_y(geom)

    if (width_wall, thickness_wall) == (thickness_wall_to_rotate, width_wall_to_rotate):
        metrics["right_location"] = True

    if not metrics["right_location"]:
        # if not rotated properly, do not give credits for not changing the size (because score would be > 0 by simply doing nothing)
        return metrics

    # dimensions
    if height_wall == height_wall_to_rotate:
        # height simply did not change
        if (width_wall, thickness_wall) == (thickness_wall_to_rotate, width_wall_to_rotate) or (width_wall, thickness_wall) == (width_wall_to_rotate, thickness_wall_to_rotate):
            # width and thickness either aren't changed or swapped
            metrics["right_dimensions"] = True

    return metrics

#execute_test("../ifc/Ifc4_SampleHouse.ifc", "../ifc/Ifc4_SampleHouse.ifc", {})
#execute_test("../ifc/basic_tasks.ifc", "../ifc/basic_tasks.ifc", {})