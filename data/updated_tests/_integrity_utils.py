import ifcopenshell

from data.tests.integrity_utils import check_integrity


def run_integrity_check(
    ifc_file,
    edited_ifc_file,
    *,
    target_guids=None,
    compare_properties=True,
    compare_hierarchy=False,
    ignore_classes=None,
    clash_mode="collision",
    allow_touching=False,
    intersection_tolerance=0.002,
    clearance=0.05,
    check_all=True,
    clash_include_classes=None,
    clash_exclude_classes=None,
    geometry_settings=None,
):
    ifc_original = ifcopenshell.open(ifc_file)
    ifc_edited = ifcopenshell.open(edited_ifc_file)

    result = check_integrity(
        ifc_original,
        ifc_edited,
        list_of_targets=sorted(set(target_guids)) if target_guids else None,
        compare_properties=compare_properties,
        compare_hierarchy=compare_hierarchy,
        ignore_classes=ignore_classes,
        clash_mode=clash_mode,
        allow_touching=allow_touching,
        intersection_tolerance=intersection_tolerance,
        clearance=clearance,
        check_all=check_all,
        clash_include_classes=clash_include_classes,
        clash_exclude_classes=clash_exclude_classes,
        geometry_settings=geometry_settings,
    )

    return bool(result.get("integrity_constraint", False))


def filled_opening_guid(ifc_model, element_guid):
    try:
        element = ifc_model.by_guid(element_guid)
    except Exception:
        return None

    for relation in ifc_model.by_type("IfcRelFillsElement"):
        try:
            if relation.RelatedBuildingElement == element:
                opening = relation.RelatingOpeningElement
                return getattr(opening, "GlobalId", None)
        except Exception:
            continue

    return None


def guids_for_type(ifc_model, ifc_type):
    return [
        getattr(element, "GlobalId", None)
        for element in ifc_model.by_type(ifc_type)
        if getattr(element, "GlobalId", None)
    ]
