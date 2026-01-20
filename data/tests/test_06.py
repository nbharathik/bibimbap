def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Provide the area in square meters of the room with id 2UsXAbj6n0fwEWqdkVuHyo."""
    metrics = {
        "right_answer": False # right area provided
    }

    area = 150.0
    predicted_area = model_output["area"]

    metrics["right_answer"] = abs(area - predicted_area) < 0.1

    return metrics

