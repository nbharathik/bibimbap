import math
import multiprocessing
from typing import Any, Dict, Iterable, Optional, Sequence, Set, Tuple

import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element
import ifcopenshell.util.placement


# -----------------------------
# Generic helpers
# -----------------------------

def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def _rooted_elements_by_guid(ifc) -> Dict[str, Any]:
    result = {}
    for elem in ifc.by_type("IfcRoot"):
        guid = getattr(elem, "GlobalId", None)
        if guid:
            result[guid] = elem
    return result


def _round_float(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _freeze(value: Any, float_digits: int = 6) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
        return _round_float(value, float_digits)
    if isinstance(value, np.ndarray):
        return _freeze(value.tolist(), float_digits)
    if isinstance(value, (list, tuple, set)):
        return tuple(_freeze(v, float_digits) for v in value)
    if isinstance(value, dict):
        return tuple(sorted((str(k), _freeze(v, float_digits)) for k, v in value.items()))
    if hasattr(value, "GlobalId"):
        return ("IFC_ENTITY", value.is_a(), getattr(value, "GlobalId", None))
    if hasattr(value, "id") and callable(value.id):
        try:
            return ("IFC_REF", value.is_a(), value.id())
        except Exception:
            pass
    return str(value)


def _matrix_from_object_placement(element) -> Optional[Tuple[Tuple[float, ...], ...]]:
    placement = getattr(element, "ObjectPlacement", None)
    if placement is None:
        return None
    try:
        m = ifcopenshell.util.placement.get_local_placement(placement)
        arr = np.asarray(m, dtype=float)
        return tuple(tuple(_round_float(v) for v in row) for row in arr)
    except Exception:
        return None


def _hierarchy_signature(element) -> Tuple[Any, Any]:
    try:
        container = ifcopenshell.util.element.get_container(element)
        container_sig = None if container is None else (container.is_a(), getattr(container, "GlobalId", None))
    except Exception:
        container_sig = None

    try:
        parent = ifcopenshell.util.element.get_parent(element)
        parent_sig = None if parent is None else (parent.is_a(), getattr(parent, "GlobalId", None))
    except Exception:
        parent_sig = None

    return container_sig, parent_sig


def _property_signature(element) -> Any:
    try:
        psets = ifcopenshell.util.element.get_psets(element)
        return _freeze(psets)
    except Exception:
        return None


def _element_signature(
    element,
    *,
    compare_properties: bool = True,
    compare_hierarchy: bool = False,
) -> Dict[str, Any]:
    sig = {
        "ifc_class": element.is_a(),
        "placement": _matrix_from_object_placement(element),
    }

    if compare_hierarchy:
        container_sig, parent_sig = _hierarchy_signature(element)
        sig["container"] = container_sig
        sig["parent"] = parent_sig

    if compare_properties:
        sig["psets"] = _property_signature(element)

    return sig


def _infer_target_guids(
    ifc_old,
    ifc_new,
    list_of_targets: Optional[Sequence[str]],
) -> Set[str]:
    if list_of_targets:
        return set(list_of_targets)

    old_guids = set(_rooted_elements_by_guid(ifc_old).keys())
    new_guids = set(_rooted_elements_by_guid(ifc_new).keys())
    return new_guids - old_guids


# -----------------------------
# 1) Non-target preservation
# -----------------------------

def non_target_elements_unchanged(
    ifc_old,
    ifc_new,
    list_of_targets: Optional[Sequence[str]] = None,
    *,
    compare_properties: bool = True,
    compare_hierarchy: bool = False,
    ignore_classes: Optional[Iterable[str]] = None,
) -> bool:
    target_guids = _infer_target_guids(ifc_old, ifc_new, list_of_targets)
    ignored: Set[str] = set(ignore_classes or [])

    old_by_guid = _rooted_elements_by_guid(ifc_old)
    new_by_guid = _rooted_elements_by_guid(ifc_new)

    old_non_target_guids = {
        g for g, e in old_by_guid.items()
        if g not in target_guids and e.is_a() not in ignored
    }

    for guid in old_non_target_guids:
        old_elem = old_by_guid[guid]
        new_elem = new_by_guid.get(guid)

        if new_elem is None:
            return False

        old_sig = _element_signature(
            old_elem,
            compare_properties=compare_properties,
            compare_hierarchy=compare_hierarchy,
        )
        new_sig = _element_signature(
            new_elem,
            compare_properties=compare_properties,
            compare_hierarchy=compare_hierarchy,
        )

        if old_sig != new_sig:
            return False

    return True


# -----------------------------
# 2) Clash integrity
# -----------------------------

def _iter_clashable_products(
    ifc,
    *,
    include_classes: Optional[Iterable[str]] = None,
    exclude_classes: Optional[Iterable[str]] = None,
) -> Iterable[Any]:
    include_set = set(include_classes or [])
    exclude_set = set(exclude_classes or [])

    for elem in ifc.by_type("IfcProduct"):
        guid = getattr(elem, "GlobalId", None)
        if not guid:
            continue

        if include_set and elem.is_a() not in include_set:
            continue

        if elem.is_a() in exclude_set:
            continue

        rep = getattr(elem, "Representation", None)
        if rep is None:
            continue

        reps = getattr(rep, "Representations", None)
        if not reps:
            continue

        yield elem


def _default_geom_settings():
    settings = ifcopenshell.geom.settings()

    # Recommended for analysis-style workflows so all shape coordinates are placed
    # in model/world space rather than left in local placement coordinates.
    try:
        settings.set("use-world-coords", True)
    except Exception:
        pass

    # Helps some problematic topologies, though it is not a guaranteed fix.
    try:
        settings.set("unify-shapes", True)
    except Exception:
        pass

    return settings


def _build_geom_tree(
    ifc,
    *,
    geometry_settings: Optional[Any] = None,
):
    """
    More reliable than tree.add_file(...) for clash workflows:
    populate the tree through the geometry iterator.
    """
    settings = geometry_settings or _default_geom_settings()
    tree = ifcopenshell.geom.tree()

    iterator = ifcopenshell.geom.iterator(
        settings,
        ifc,
        multiprocessing.cpu_count(),
    )

    if iterator.initialize():
        while True:
            tree.add_element(iterator.get())
            if not iterator.next():
                break

    return tree


def _entity_guid_from_clash_side(side) -> Optional[str]:
    """
    clash.a / clash.b are wrapper-side objects. In practice, get_argument(0)
    is the reliable way to pull the IFC GlobalId, matching public examples.
    """
    if side is None:
        return None

    guid = getattr(side, "GlobalId", None)
    if guid:
        return guid

    try:
        guid = side.get_argument(0)
        if isinstance(guid, str) and guid:
            return guid
    except Exception:
        pass

    return None


def _collect_geom_tree_clash_pairs(
    ifc,
    *,
    focus_guids: Optional[Set[str]] = None,
    clash_mode: str = "collision",
    allow_touching: bool = False,
    intersection_tolerance: float = 0.002,
    clearance: float = 0.05,
    check_all: bool = True,
    include_classes: Optional[Iterable[str]] = None,
    exclude_classes: Optional[Iterable[str]] = None,
    geometry_settings: Optional[Any] = None,
) -> Set[Tuple[str, str]]:
    elems = list(
        _iter_clashable_products(
            ifc,
            include_classes=include_classes,
            exclude_classes=exclude_classes,
        )
    )
    if not elems:
        return set()

    tree = _build_geom_tree(ifc, geometry_settings=geometry_settings)

    if clash_mode == "collision":
        clashes = tree.clash_collision_many(
            elems,
            elems,
            allow_touching=allow_touching,
        )
    elif clash_mode == "intersection":
        clashes = tree.clash_intersection_many(
            elems,
            elems,
            tolerance=intersection_tolerance,
            check_all=check_all,
        )
    elif clash_mode == "clearance":
        clashes = tree.clash_clearance_many(
            elems,
            elems,
            clearance=clearance,
            check_all=check_all,
        )
    else:
        raise ValueError(
            "Unsupported clash_mode. Expected one of: "
            "'collision', 'intersection', 'clearance'."
        )

    pairs: Set[Tuple[str, str]] = set()

    for clash in clashes:
        a_guid = _entity_guid_from_clash_side(getattr(clash, "a", None))
        b_guid = _entity_guid_from_clash_side(getattr(clash, "b", None))

        if not a_guid or not b_guid:
            continue
        if a_guid == b_guid:
            continue
        if focus_guids is not None and a_guid not in focus_guids and b_guid not in focus_guids:
            continue

        pairs.add(tuple(sorted((a_guid, b_guid))))

    return pairs


def debug_clashes(
    ifc,
    *,
    include_classes: Optional[Iterable[str]] = None,
    clash_mode: str = "collision",
    allow_touching: bool = False,
    intersection_tolerance: float = 0.002,
    clearance: float = 0.05,
    check_all: bool = True,
    geometry_settings: Optional[Any] = None,
):
    """
    Debug helper: returns full clash records instead of only pairs.
    """
    elems = list(
        _iter_clashable_products(
            ifc,
            include_classes=include_classes,
        )
    )
    tree = _build_geom_tree(ifc, geometry_settings=geometry_settings)

    if clash_mode == "collision":
        clashes = tree.clash_collision_many(elems, elems, allow_touching=allow_touching)
    elif clash_mode == "intersection":
        clashes = tree.clash_intersection_many(
            elems, elems, tolerance=intersection_tolerance, check_all=check_all
        )
    elif clash_mode == "clearance":
        clashes = tree.clash_clearance_many(
            elems, elems, clearance=clearance, check_all=check_all
        )
    else:
        raise ValueError(clash_mode)

    result = []
    for clash in clashes:
        result.append(
            {
                "a_guid": _entity_guid_from_clash_side(getattr(clash, "a", None)),
                "b_guid": _entity_guid_from_clash_side(getattr(clash, "b", None)),
                "clash_type": getattr(clash, "clash_type", None),
                "distance": getattr(clash, "distance", None),
                "p1": list(getattr(clash, "p1", [])) if getattr(clash, "p1", None) is not None else None,
                "p2": list(getattr(clash, "p2", [])) if getattr(clash, "p2", None) is not None else None,
            }
        )
    return result


def check_clash_integrity(
    ifc_old,
    ifc_new,
    *,
    list_of_targets: Optional[Sequence[str]] = None,
    clash_mode: str = "collision",
    allow_touching: bool = False,
    intersection_tolerance: float = 0.002,
    clearance: float = 0.05,
    check_all: bool = True,
    include_classes: Optional[Iterable[str]] = None,
    exclude_classes: Optional[Iterable[str]] = None,
    geometry_settings: Optional[Any] = None,
) -> bool:
    target_guids = _infer_target_guids(ifc_old, ifc_new, list_of_targets)
    focus_guids = target_guids if target_guids else None

    old_pairs = _collect_geom_tree_clash_pairs(
        ifc_old,
        focus_guids=focus_guids,
        clash_mode=clash_mode,
        allow_touching=allow_touching,
        intersection_tolerance=intersection_tolerance,
        clearance=clearance,
        check_all=check_all,
        include_classes=include_classes,
        exclude_classes=exclude_classes,
        geometry_settings=geometry_settings,
    )
    new_pairs = _collect_geom_tree_clash_pairs(
        ifc_new,
        focus_guids=focus_guids,
        clash_mode=clash_mode,
        allow_touching=allow_touching,
        intersection_tolerance=intersection_tolerance,
        clearance=clearance,
        check_all=check_all,
        include_classes=include_classes,
        exclude_classes=exclude_classes,
        geometry_settings=geometry_settings,
    )
    new_clashes_introduced = new_pairs - old_pairs
    return len(new_clashes_introduced) == 0


# -----------------------------
# 3) Overall integrity check
# -----------------------------

def check_integrity(
    ifc_old,
    ifc_new,
    list_of_targets: Optional[Sequence[str]] = None,
    *,
    compare_properties: bool = True,
    compare_hierarchy: bool = False,
    ignore_classes: Optional[Iterable[str]] = None,
    clash_mode: str = "collision",
    allow_touching: bool = False,
    intersection_tolerance: float = 0.002,
    clearance: float = 0.05,
    check_all: bool = True,
    clash_include_classes: Optional[Iterable[str]] = None,
    clash_exclude_classes: Optional[Iterable[str]] = None,
    geometry_settings: Optional[Any] = None,
) -> Dict[str, bool]:
    target_guids = _infer_target_guids(ifc_old, ifc_new, list_of_targets)

    non_target_ok = non_target_elements_unchanged(
        ifc_old,
        ifc_new,
        list_of_targets=target_guids,
        compare_properties=compare_properties,
        compare_hierarchy=compare_hierarchy,
        ignore_classes=ignore_classes,
    )

    clash_ok = check_clash_integrity(
        ifc_old,
        ifc_new,
        list_of_targets=target_guids,
        clash_mode=clash_mode,
        allow_touching=allow_touching,
        intersection_tolerance=intersection_tolerance,
        clearance=clearance,
        check_all=check_all,
        include_classes=clash_include_classes,
        exclude_classes=clash_exclude_classes,
        geometry_settings=geometry_settings,
    )

    print("Integrity Check Result:")
    print("- Non-target elements unchanged:", non_target_ok)
    print("- No new clashes:", clash_ok)

    return {
        "non_target_elements_unchanged": non_target_ok,
        "no_new_clashes": clash_ok,
        "integrity_constraint": non_target_ok and clash_ok,
    }


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