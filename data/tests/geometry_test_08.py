from data.tests.utils import extract_numeric_value


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: provide the distance between the longest walls.

    Expected answer: 4.0 meters.
    Tight tolerance is allowed (e.g. rounding like 4 or 4.00).
    """

    expected = 4.0
    abs_tol = 0.01

    predicted = extract_numeric_value(model_output)
    ok = predicted is not None and abs(predicted - expected) <= abs_tol

    return {"right_answer": ok}
