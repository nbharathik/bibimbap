import ifcopenshell


COLUMN_GUID = "0lwZAgQMb7yAIJTmmcGlwc"

# Expected correct answer
CORRECT_WALL_GUID = "0lwZAgQMb7yAIJTmmcGloi"

# Partial credit alternative (as specified)
PARTIAL_WALL_GUID = "0lwZAgQMb7yAIJTmmcGlnB" # This is also very close, but not the closest


def _safe_by_guid(ifc, guid: str):
    try:
        return ifc.by_guid(guid)
    except Exception:
        return None


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: delete the wall closest to the given column (by midpoint-to-wall-edge distance).

    Scoring:
    - score = 1.0 if CORRECT_WALL_GUID is deleted
    - score = 0.2 if CORRECT_WALL_GUID is not deleted but almost nearest wall is deleted
    - score = 0.0 otherwise

    Metrics are numeric-friendly (not only booleans).
    """

    metrics = {
        "score": 0.0,
    }

    try:
        ifc_edited = ifcopenshell.open(edited_ifc_file)
    except Exception:
        return metrics

    column_exists = _safe_by_guid(ifc_edited, COLUMN_GUID) is not None
    
    if not column_exists:
        return metrics

    wall_deleted = _safe_by_guid(ifc_edited, CORRECT_WALL_GUID) is None
    partial_wall_deleted = _safe_by_guid(ifc_edited, PARTIAL_WALL_GUID) is None

    if wall_deleted:
        metrics["score"] = 1.0
    elif partial_wall_deleted:
        metrics["score"] = 0.2

    return metrics
