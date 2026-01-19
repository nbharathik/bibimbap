# 1NO2FmQyX8Dx48Vy4bqK11 and 1NO2FmQyX8Dx48Vy4bqK9m

def execute_test(ifc_file, edited_ifc_file, model_output):
    """Prompt: Provide the ids of the slabs that close the room with the id 3Vyqk8cSj8TOuAk6zHUwKx."""
    return {"right_answer": set(model_output["global_ids"]) == {"1NO2FmQyX8Dx48Vy4bqK11", "1NO2FmQyX8Dx48Vy4bqK9m"}}