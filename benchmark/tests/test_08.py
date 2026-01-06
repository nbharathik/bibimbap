import math

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Provide the volume of the room with id 2UsXAbj6n0fwEWqdkVuHyo."""
    metrics = {
        "right_answer": False # right volume provided
    }

    volume = 457.2
    predicted_volume = model_output["volume"]

    metrics["right_answer"] = math.isclose(volume, round(predicted_volume, 1))

    return metrics