def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Take off the length of the wall with id 22hyxvAPr65PFt9WZfHSKC."""
    metrics = {
        "right_answer": False # right length provided
    }

    length = 10.2
    predicted_length = model_output["length"]

    metrics["right_answer"] = length == predicted_length

    return metrics

