
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": model_output["global_id"] == "3$LLWIV1uGcX2kUN2Ag9uo"
    }