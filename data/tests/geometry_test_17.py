import ifcopenshell

WALL_GUIDS = [
    "1G$Ejw1Tn27RsUWQGSEz6r",
    "1G$Ejw1Tn27RsUWQGSEz6s",
    "1G$Ejw1Tn27RsUWQGSEz59",
    "1G$Ejw1Tn27RsUWQGSEz58",
    "1u4oG4Ltr15fMWjwJ4pN4F",
    "1u4oG4Ltr15fMWjwJ4pNPJ",
    "1u4oG4Ltr15fMWjwJ4pNUQ",
    "1u4oG4Ltr15fMWjwJ4pN5R",
    "1u4oG4Ltr15fMWjwJ4pNOG",
    "1u4oG4Ltr15fMWjwJ4pNV8",
]


def _exists(ifc, guid: str) -> bool:
    try:
        return ifc.by_guid(guid) is not None
    except Exception:
        return False


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: remove exterior walls separated from the main structure (ground floor).

    Simple check: all specified wall GUIDs are absent in the edited IFC.
    """

    # metrics = {f"deleted_{i+1}": False for i in range(len(WALL_GUIDS))}
    metrics = {
        "object_not_exists": False,
        "integrity_constraint": False,
    }

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics
    
    all_deleted = all(
        not _exists(ifc_edited, guid) for guid in WALL_GUIDS
    )
        
    metrics["object_not_exists"] = all_deleted
    metrics["integrity_constraint"] = all_deleted

    return metrics
