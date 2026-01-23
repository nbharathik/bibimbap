
def execute_test(ifc_file, edited_ifc_file, model_output):
    return {
        "right_answer": model_output["global_id"] == "1k$xn8F5n4Fh7djrSbibhp"
    }