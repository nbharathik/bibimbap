import ifcopenshell
import ifcopenshell.util.element

from data.tests.integrity_utils import non_target_elements_unchanged

def spatial_containment_deleted(original_ifc, edited_ifc, target_guid):
    """Check if the spatial containment relationship was deleted."""

    original_element = original_ifc.by_guid(target_guid)

    container = ifcopenshell.util.element.get_container(original_element)
    container_guid = getattr(container, "GlobalId", None)
    try:
        edited_container = edited_ifc.by_guid(container_guid)
        contained = ifcopenshell.util.element.get_contained(edited_container)
    except RuntimeError:
        return False

    if original_element not in contained:
        return True

    return False


def wall_connections_deleted(original_ifc, edited_ifc, target_guid):
    """Check if the wall connections were deleted."""
    original_wall = original_ifc.by_guid(target_guid)

    original_connections = original_wall.ConnectedTo + original_wall.ConnectedFrom
    original_set = set(map(lambda x: x.GlobalId, original_connections))
    edited_connections = edited_ifc.by_type("IfcRelConnectsPathElements")

    edited_set = set(map(lambda x: x.GlobalId, edited_connections))

    if set(original_set).issubset(set(edited_set)):
        # original relationships still exist in the edited file
        return False
    return True

def openings_deleted(original_ifc, edited_ifc, target_guid):
    """Check if the openings were deleted. Only for windows and doors."""
    # for windows and doors
    original_element = original_ifc.by_guid(target_guid)
    original_void = ifcopenshell.util.element.get_filled_void(original_element)
    original_void_guid = getattr(original_void, "GlobalId", None)
    if not original_void_guid:
        return True
    try:
        edited_ifc.by_guid(original_void_guid)
        return False
    except RuntimeError:
        return True

def filling_deleted(original_ifc, edited_ifc, target_guid):
    """Check if the filling of an opening was also deleted."""
    original_element = original_ifc.by_guid(target_guid)
    original_filling_rel = original_element.FillsVoids
    original_filling = None
    if original_filling_rel:
        original_filling = original_filling_rel.RelatedBuildingElement

    if original_filling:
        original_filling_guid = getattr(original_filling, "GlobalId", None)
        try:
            edited_ifc.by_guid(original_filling_guid)
            return False
        except RuntimeError:
            return True

    return True

def aggregations_deleted(original_ifc, edited_ifc, target_guid):
    """Check if the aggregations were deleted."""
    # check if element was aggregated or aggregates others and delete accordingly
    original_element = original_ifc.by_guid(target_guid)

    # element was aggregated
    original_parent = ifcopenshell.util.element.get_aggregate(original_element)
    if original_parent:
        original_parent_guid = getattr(original_parent, "GlobalId", None)

        edited_parent = edited_ifc.by_guid(original_parent_guid)
        edited_parent_parts = ifcopenshell.util.element.get_parts(edited_parent)
        edited_parent_parts_guids = list(map(lambda x: x.GlobalId, edited_parent_parts))

        if target_guid in edited_parent_parts_guids:
            # target id still in edited ifc file parts -> relationship not deleted
            return False


    # element aggregated others -> others need to be deleted as well?
    original_parts = ifcopenshell.util.element.get_parts(original_element)
    if original_parts:
        original_parts_guids = list(map(lambda x: x.GlobalId, original_parts))

        for part_guid in original_parts_guids:
            try:
                edited_ifc.by_guid(part_guid)
                # found a part of the aggregation in the edited file -> not deleted -> return false
                return False
            except RuntimeError:
                continue

    return True


def run_delete_integrity_check(ifc_file, edited_ifc_file, target_guids):
    """Run the integrity check for the delete task."""

    original_ifc = ifcopenshell.open(ifc_file)
    edited_ifc = ifcopenshell.open(edited_ifc_file)
    delete_integrity = True
    for target_guid in target_guids:
        sub_categories = [
            wall_connections_deleted(original_ifc, edited_ifc, target_guid),
            spatial_containment_deleted(original_ifc, edited_ifc, target_guid),
            openings_deleted(original_ifc, edited_ifc, target_guid),
            aggregations_deleted(original_ifc, edited_ifc, target_guid)
        ]
        print(sub_categories)
        delete_integrity = delete_integrity and all(sub_categories)

    return delete_integrity and non_target_elements_unchanged(original_ifc, edited_ifc, target_guids)
