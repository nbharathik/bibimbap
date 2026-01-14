import re
from typing import Any


EXPECTED = {
    "2I2XyofMDDYhKncvMedHww",
    "2I2XyofMDDYhKncvMedHX0",
    "2I2XyofMDDYhKncvMedH$i",
}


def _normalize_id(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    text = text.replace("GlobalId", "").replace("globalid", "")
    text = text.replace("=", " ")
    text = text.replace(":", " ")
    text = text.strip().strip('"\'')

    tokens = text.split()
    if not tokens:
        return None

    return tokens[-1]


def _extract_ids(model_output: Any) -> list[str]:
    if isinstance(model_output, dict):
        for key in ("wall_ids", "wallIds", "ids", "guids", "global_ids", "globalIds"):
            if key in model_output and isinstance(model_output[key], list):
                normalized = []
                for item in model_output[key]:
                    gid = _normalize_id(item)
                    if gid:
                        normalized.append(gid)
                return normalized

        text = str(model_output)
    elif isinstance(model_output, list):
        normalized = []
        for item in model_output:
            gid = _normalize_id(item)
            if gid:
                normalized.append(gid)
        return normalized
    else:
        text = str(model_output)

    candidates = re.findall(r"[0-9A-Za-z_\$]{10,30}", text)
    normalized = []
    for cand in candidates:
        gid = _normalize_id(cand)
        if gid:
            normalized.append(gid)
    return normalized


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: provide the ids of the walls that shape a triangle.

    Answer IDs can be in any order.
    Requirements:
    - the output contains ALL expected GUIDs
    - the output contains EXACTLY 3 ids (no extras)
    """

    predicted_ids = _extract_ids(model_output)
    predicted_set = set(predicted_ids)

    contains_all_three = EXPECTED.issubset(predicted_set)
    has_exactly_three = len(predicted_set) == 3

    return {
        "contains_all_three": contains_all_three,
        "has_exactly_three": has_exactly_three,
    }
