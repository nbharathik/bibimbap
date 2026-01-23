
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": model_output["global_id"] == "1NrLJManH9euSq4FIPenFQ"
    }