import re
from typing import Any


def _parse_first_number(text: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:[\.,]\d+)?", text)
    if not match:
        return None

    raw = match.group(0)

    if "," in raw and "." in raw:
        last_comma = raw.rfind(",")
        last_dot = raw.rfind(".")
        if last_comma > last_dot:
            # 1.234,56 -> 1234.56
            raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
        else:
            # 1,234.56 -> 1234.56
            raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")

    try:
        return float(raw)
    except ValueError:
        return None


def extract_numeric_value(model_output: Any) -> float | None:
    if model_output is None:
        return None

    if isinstance(model_output, (int, float)):
        return float(model_output)

    if isinstance(model_output, dict):
        for key in ("value", "answer", "result", "area", "count"):
            if key in model_output:
                value = model_output[key]
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    parsed = _parse_first_number(value)
                    if parsed is not None:
                        return parsed
        return _parse_first_number(str(model_output))

    return _parse_first_number(str(model_output))


def within_tolerance(predicted: float, expected: float, abs_tol: float, rel_tol: float) -> bool:
    tol = max(abs_tol, rel_tol * abs(expected))
    return abs(predicted - expected) <= tol
