from data.tests.utils2 import extract_numeric_value, within_tolerance


def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: provide total inner length of the two walls with given GlobalIds.

    Expected answer: 5.9m with tight tolerance.
    """

    expected = 5.9
    abs_tol = 0.01
    rel_tol = 0.0

    predicted = extract_numeric_value(model_output)
    ok = predicted is not None and within_tolerance(predicted, expected, abs_tol, rel_tol)

    return {"right_answer": ok}
