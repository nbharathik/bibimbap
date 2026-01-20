def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Provide the distance, center to center, of the columns with ids 22hyxvAPr65PFt9WZfHSMr and 22hyxvAPr65PFt9WZfHSMu."""
    metrics = {
        "right_answer": False # right distance provided
    }

    distance = 10.0
    predicted_distance = model_output["distance"]

    metrics["right_answer"] = abs(distance - predicted_distance) < 0.1

    return metrics

