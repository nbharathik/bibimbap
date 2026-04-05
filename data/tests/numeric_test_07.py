from data.tests.utils2 import extract_numeric_value, within_tolerance


def execute_test(ifc_file, edited_ifc_file, model_output):
    expected = 20.82
    abs_tol = 0.1
    rel_tol = 0.001

    predicted = extract_numeric_value(model_output)
    ok = predicted is not None and within_tolerance(predicted, expected, abs_tol, rel_tol)
    return {"right_answer": ok}
