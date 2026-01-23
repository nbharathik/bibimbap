
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": abs(model_output["volume"] - 27) < 0.1
    }