def _is_only_global_id(value: str) -> bool:
	if value is None:
		return False

	text = str(value).strip()

	allowed = {
		"1pkLoAx5P7Lwxnk7MMv3Lz",
		"\"1pkLoAx5P7Lwxnk7MMv3Lz\"",
		"'1pkLoAx5P7Lwxnk7MMv3Lz'",
	}
	return text in allowed


def execute_test(ifc_file, edited_ifc_file, model_output):
	"""Prompt: provide id of the wall that is the shortest.

	Expected answer (only): 1pkLoAx5P7Lwxnk7MMv3Lz
	"""

	expected = "1pkLoAx5P7Lwxnk7MMv3Lz"

	predicted = None
	if isinstance(model_output, dict):
		predicted = model_output.get("global_id") or model_output.get("id")
	else:
		predicted = model_output

	ok = _is_only_global_id(predicted) and str(predicted).strip().strip('"\'') == expected
	return {"correct_id": ok}
