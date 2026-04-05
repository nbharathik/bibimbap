
from data.tests.utils2 import extract_numeric_value


def execute_test(ifc_file, edited_ifc_file, model_output):
	"""Prompt: provide length (longest side) of the room that has not the shape of a square.

	Scoring:
	- Full score if the predicted value is ~7.2m.
	- Half score if the predicted value is within [6.9m, 7.4m] but not ~7.2m.
	"""

	# Sometimes it can be outer length or inner lenght of the IFC, so we can allow the answer in that range. The exact expected value is 7.2 which is midpoint of wall start to end.
	expected = 7.2
	min_accepted = 6.9
	max_accepted = 7.4

	# Tight tolerance for the "exact" target (handles rounding like 7.20)
	exact_abs_tol = 0.01

	predicted = extract_numeric_value(model_output)
	if predicted is None:
		return {"right_answer": False}

	within_range = min_accepted <= predicted <= max_accepted
	exact_7_2 = abs(predicted - expected) <= exact_abs_tol

	# Exact gets more weight
	if exact_7_2:
		within_range = True

	return {"right_answer": within_range}
