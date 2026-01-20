def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Take off the length in meters of the wall with id 22hyxvAPr65PFt9WZfHSKC."""
    metrics = {
        "right_answer": False # right length provided
    }

    length = 10.2
    predicted_length = model_output["length"]

    metrics["right_answer"] = abs(length - predicted_length) < 0.1

    return metrics

