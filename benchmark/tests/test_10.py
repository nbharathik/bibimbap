def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Provide the global id of the wall that has a length of 5m."""
    metrics = {
        "right_answer": False # right id provided
    }

    global_id = "22hyxvAPr65PFt9WZfHSP3"
    predicted_global_id = model_output["global_id"]

    metrics["right_answer"] = global_id == predicted_global_id

    return metrics

